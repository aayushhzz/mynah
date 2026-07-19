from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

MEETINGS_ROOT = Path(os.environ.get("MEETINGS_ROOT", str(_REPO_ROOT / "data" / "meetings")))
DB_PATH = Path(os.environ.get("DB_PATH", str(_REPO_ROOT / "data" / "meetings.sqlite3")))
RECORDING_STATE_PATH = Path(
    os.environ.get("RECORDING_STATE_PATH", str(_REPO_ROOT / "data" / "recording_state.json"))
)
RECORDING_SOURCES_ROOT = Path(
    os.environ.get("RECORDING_SOURCES_ROOT", str(_REPO_ROOT / "data" / "recording_sources"))
)
SYSTEM_AUDIO_RECORDER_BINARY = Path(
    os.environ.get(
        "SYSTEM_AUDIO_RECORDER_BINARY",
        str(_REPO_ROOT / "tools" / "system_audio_recorder" / "system_audio_recorder"),
    )
)
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "large-v3-turbo")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct")
