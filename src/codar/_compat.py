"""Compatibilidade com Python 3.10 (Ubuntu 22.04)."""

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

__all__ = ["tomllib"]
