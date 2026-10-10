"""Gravação atômica do buffer, sem substituir alterações externas no autosave."""

from pathlib import Path
import os
import stat
import tempfile


def write_buffer(path, text, baseline=None):
    target = Path(path).resolve()
    original = target.read_bytes() if target.exists() else None
    if baseline is not None and original != baseline:
        raise ValueError('O arquivo mudou fora do Studio. Reabra-o ou revise antes de salvar com Ctrl+S.')
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(text.encode('utf-8'))
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(mode)
        if baseline is not None and (target.read_bytes() if target.exists() else None) != original:
            raise ValueError('O arquivo mudou durante o salvamento. Autosave pausado para esta aba.')
        temporary.replace(target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return text.encode('utf-8')
