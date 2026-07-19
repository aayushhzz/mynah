from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Protocol


class ProcessHandle(Protocol):
    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class CommandRunner(Protocol):
    def start(self, cmd: list[str]) -> ProcessHandle: ...


@dataclass
class CompletedProcess:
    returncode: int
    stdout: str
    stderr: str


class SyncCommandRunner(Protocol):
    def run(self, cmd: list[str], input: str | None = None) -> CompletedProcess: ...


class SubprocessProcessHandle:
    def __init__(self, popen: subprocess.Popen):
        self._popen = popen

    def poll(self) -> int | None:
        return self._popen.poll()

    def terminate(self) -> None:
        self._popen.terminate()

    def wait(self, timeout: float | None = None) -> int:
        return self._popen.wait(timeout=timeout)


class SubprocessCommandRunner:
    def start(self, cmd: list[str]) -> ProcessHandle:
        popen = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return SubprocessProcessHandle(popen)


class SubprocessSyncCommandRunner:
    def run(self, cmd: list[str], input: str | None = None) -> CompletedProcess:
        result = subprocess.run(
            cmd,
            input=input,
            capture_output=True,
            text=True,
        )
        return CompletedProcess(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
