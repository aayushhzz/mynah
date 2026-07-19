#!/usr/bin/env python3
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_VENV_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python3"

if _VENV_PYTHON.exists() and Path(sys.executable).resolve() != _VENV_PYTHON.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

sys.path.insert(0, str(_REPO_ROOT / "src"))

from cli import main  # noqa: E402

if __name__ == "__main__":
    main()
