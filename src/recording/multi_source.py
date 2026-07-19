from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from recording.background import (
    DetachedProcessLauncher,
    NoActiveRecordingError,
    ProcessController,
    RecordingAlreadyActiveError,
    RecordingState,
    RecordingStateStore,
    SourceState,
)
from recording.recorder import EmptyRecordingError


class NoSourcesStartedError(Exception):
    pass


@dataclass
class SourceSpec:
    name: str
    build_cmd: Callable[[Path], list[str]]


class MultiSourceRecorder:
    def __init__(
        self,
        launcher: DetachedProcessLauncher,
        process_controller: ProcessController,
        state_store: RecordingStateStore,
        sources: list[SourceSpec],
        stop_timeout: float = 10.0,
        poll_interval: float = 0.2,
    ):
        self._launcher = launcher
        self._process_controller = process_controller
        self._state_store = state_store
        self._sources = sources
        self._stop_timeout = stop_timeout
        self._poll_interval = poll_interval

    def start(self, output_dir: Path, title: str | None = None) -> list[str]:
        if not self._state_store.try_claim():
            raise RecordingAlreadyActiveError("A recording is already in progress")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        started: list[SourceState] = []
        warnings: list[str] = []

        for source in self._sources:
            output_path = output_dir / f"{source.name}.wav"
            cmd = source.build_cmd(output_path)
            try:
                pid = self._launcher.launch(cmd)
            except OSError as exc:
                warnings.append(f"Failed to start source '{source.name}': {exc}")
                continue
            started.append(SourceState(name=source.name, pid=pid, output_path=str(output_path)))

        if not started:
            self._state_store.clear()
            raise NoSourcesStartedError(
                "None of the configured audio sources could be started: " + "; ".join(warnings)
            )

        self._state_store.save(RecordingState(sources=started, title=title))
        return warnings

    def is_recording(self) -> bool:
        if not self._state_store.exists():
            return False
        try:
            state = self._state_store.load()
        except NoActiveRecordingError:
            return False
        return any(self._process_controller.is_alive(source.pid) for source in state.sources)

    def stop(self) -> tuple[list[tuple[str, Path]], str | None, list[str]]:
        state = self._state_store.load()

        for source in state.sources:
            if self._process_controller.is_alive(source.pid):
                self._process_controller.terminate(source.pid)

        deadline = time.monotonic() + self._stop_timeout
        while (
            any(self._process_controller.is_alive(source.pid) for source in state.sources)
            and time.monotonic() < deadline
        ):
            time.sleep(self._poll_interval)

        for source in state.sources:
            if self._process_controller.is_alive(source.pid):
                self._process_controller.kill(source.pid)

        self._state_store.clear()

        valid_sources: list[tuple[str, Path]] = []
        warnings: list[str] = []
        for source in state.sources:
            output_path = Path(source.output_path)
            if not output_path.exists() or output_path.stat().st_size == 0:
                warnings.append(f"Source '{source.name}' produced no usable audio: {output_path}")
                continue
            valid_sources.append((source.name, output_path))

        if not valid_sources:
            raise EmptyRecordingError(
                "No source produced usable audio: " + "; ".join(warnings)
            )

        return valid_sources, state.title, warnings
