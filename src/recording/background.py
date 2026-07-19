from __future__ import annotations

import json
import os
import signal
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


class RecordingAlreadyActiveError(Exception):
    pass


class NoActiveRecordingError(Exception):
    pass


@dataclass
class SourceState:
    name: str
    pid: int
    output_path: str


@dataclass
class RecordingState:
    sources: list[SourceState]
    title: str | None = None


class RecordingStateStore:
    def __init__(self, state_path: Path):
        self._state_path = Path(state_path)

    def exists(self) -> bool:
        return self._state_path.exists()

    def try_claim(self) -> bool:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self._state_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps({"sources": [], "title": None}))
        return True

    def save(self, state: RecordingState) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(asdict(state)))

    def load(self) -> RecordingState:
        if not self._state_path.exists():
            raise NoActiveRecordingError("No active recording found")
        try:
            raw = json.loads(self._state_path.read_text())
            sources = [SourceState(**source) for source in raw["sources"]]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            self.clear()
            raise NoActiveRecordingError(f"Recording state file was corrupt and has been cleared: {exc}") from exc
        return RecordingState(sources=sources, title=raw.get("title"))

    def clear(self) -> None:
        self._state_path.unlink(missing_ok=True)


class DetachedProcessLauncher(Protocol):
    def launch(self, cmd: list[str]) -> int: ...


class ProcessController(Protocol):
    def is_alive(self, pid: int) -> bool: ...

    def terminate(self, pid: int) -> None: ...

    def kill(self, pid: int) -> None: ...


class OSDetachedProcessLauncher:
    def launch(self, cmd: list[str]) -> int:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return process.pid


class OSProcessController:
    def is_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def terminate(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def kill(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
