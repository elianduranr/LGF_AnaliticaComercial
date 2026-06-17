from __future__ import annotations

import os
import re
from pathlib import Path


_PS_ENV_RE = re.compile(
    r"""^\s*\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(['"])(.*)\2\s*$"""
)


def load_local_credentials(root: str | Path | None = None, *, override: bool = False) -> dict[str, str]:
    """Carga asignaciones $env:NAME = "value" desde configurar_credenciales.local.ps1."""
    base = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    path = base / "configurar_credenciales.local.ps1"
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = _PS_ENV_RE.match(line)
        if not match:
            continue
        name, _, value = match.groups()
        if override or not os.getenv(name):
            os.environ[name] = value
        loaded[name] = os.environ.get(name, value)
    return loaded
