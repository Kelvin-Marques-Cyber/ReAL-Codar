"""Guarda de memória: mede RSS (daemon + filhos), aplica limites duros do SO e reage a pressão.

Camadas (da mais forte para a mais fraca):
  1. Limite do kernel: cgroup v2 MemoryMax (Linux, via systemd-run) ou Job Object (Windows).
  2. Watchdog: acima de soft_pct limpa caches/KV e devolve heap ao SO; acima de hard_pct
     descarrega o modelo (o maior consumidor) antes que o kernel precise matar o processo.
  3. Orçamentos fixos: n_ctx/n_batch fixos, filas e caches com tamanho máximo, uma única thread de inferência.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


def rss_bytes(pid: int | None = None) -> int:
    pid = pid or os.getpid()
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/statm", encoding="ascii") as fh:
                return int(fh.read().split()[1]) * PAGE
        except (OSError, ValueError, IndexError):
            return 0
    if sys.platform == "win32":
        return _win_rss(pid)
    try:
        import psutil  # type: ignore[import-not-found]

        return int(psutil.Process(pid).memory_info().rss)
    except Exception:
        pass
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=2)
        return int(out.stdout.strip() or 0) * 1024
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0


def _win_rss(pid: int) -> int:  # pragma: no cover - Windows
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)  # QUERY_LIMITED_INFORMATION | VM_READ
    if not handle:
        return 0
    try:
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return int(pmc.WorkingSetSize)
        return 0
    finally:
        kernel32.CloseHandle(handle)


def cgroup_limit() -> int | None:
    """Limite de memória do cgroup v2 do processo (bytes) ou None."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        for line in Path("/proc/self/cgroup").read_text().splitlines():
            if line.startswith("0::"):
                rel = line[3:].strip()
                value = (Path("/sys/fs/cgroup") / rel.lstrip("/") / "memory.max").read_text().strip()
                return None if value == "max" else int(value)
    except (OSError, ValueError):
        return None
    return None


def apply_job_limit(limit_bytes: int) -> bool:  # pragma: no cover - Windows
    """Coloca o próprio processo num Job Object com limite de memória commitada (teto duro no Windows)."""
    if sys.platform != "win32":
        return False
    from ctypes import wintypes

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOperationCount", "WriteOperationCount",
                                                    "OtherOperationCount", "ReadTransferCount",
                                                    "WriteTransferCount", "OtherTransferCount")]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return False
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = 0x00000100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
    info.ProcessMemoryLimit = limit_bytes
    if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        return False
    return bool(kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()))


@dataclass
class MemState:
    rss_mb: float = 0.0
    child_mb: float = 0.0
    peak_mb: float = 0.0
    level: str = "ok"  # ok | soft | hard
    enforcement: str = "soft"
    soft_events: int = 0
    hard_events: int = 0


class MemGuard:
    def __init__(self, mcfg: dict) -> None:
        self.budget = int(mcfg.get("budget_mb", 3072)) * 1048576
        self.soft = self.budget * float(mcfg.get("soft_pct", 80)) / 100
        self.hard = self.budget * float(mcfg.get("hard_pct", 92)) / 100
        self.state = MemState()
        limit = cgroup_limit()
        if limit:
            self.state.enforcement = f"cgroup:{limit // 1048576}MB"
        elif os.environ.get("CODAR_JOB_LIMIT"):
            self.state.enforcement = f"job:{int(os.environ['CODAR_JOB_LIMIT']) // 1048576}MB"

    def sample(self, children: list[int | None]) -> MemState:
        own = rss_bytes()
        kids = sum(rss_bytes(pid) for pid in children if pid)
        total = own + kids
        st = self.state
        st.rss_mb = round(own / 1048576, 1)
        st.child_mb = round(kids / 1048576, 1)
        st.peak_mb = max(st.peak_mb, round(total / 1048576, 1))
        st.level = "hard" if total > self.hard else "soft" if total > self.soft else "ok"
        return st

    def as_dict(self) -> dict:
        st = self.state
        return {"rss_mb": st.rss_mb, "child_mb": st.child_mb, "total_mb": round(st.rss_mb + st.child_mb, 1),
                "peak_mb": st.peak_mb, "budget_mb": self.budget // 1048576,
                "soft_mb": round(self.soft / 1048576), "hard_mb": round(self.hard / 1048576), "level": st.level,
                "enforcement": st.enforcement, "soft_events": st.soft_events, "hard_events": st.hard_events}
