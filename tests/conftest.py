from __future__ import annotations

from pathlib import Path

import pytest

from common.process import CompletedProcess
from transcription.whisper_model import TranscriptionInfo


class FakeProcessHandle:
    def __init__(self):
        self.poll_returncode: int | None = None
        self.terminated = False
        self.wait_returncode = 0

    def poll(self) -> int | None:
        return self.poll_returncode

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        return self.wait_returncode


class FakeCommandRunner:
    def __init__(self, write_file_on_start: bool = True, file_content: bytes = b"RIFF....WAVEfmt "):
        self.write_file_on_start = write_file_on_start
        self.file_content = file_content
        self.started_cmds: list[list[str]] = []
        self.handle: FakeProcessHandle | None = None

    def start(self, cmd: list[str]) -> FakeProcessHandle:
        self.started_cmds.append(cmd)
        if self.write_file_on_start:
            output_path = Path(cmd[-1])
            output_path.write_bytes(self.file_content)
        self.handle = FakeProcessHandle()
        return self.handle


class FakeSyncCommandRunner:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[list[str]] = []
        self.inputs_received: list[str | None] = []

    def run(self, cmd: list[str], input: str | None = None) -> CompletedProcess:
        self.calls.append(cmd)
        self.inputs_received.append(input)
        return CompletedProcess(returncode=self.returncode, stdout=self.stdout, stderr=self.stderr)


class FakeTranscriptionModel:
    def __init__(self, canned_segments, canned_info: TranscriptionInfo | None = None):
        self.canned_segments = canned_segments
        self.canned_info = canned_info or TranscriptionInfo(language="en", duration=0.0)

    def transcribe(self, audio_path):
        return self.canned_segments, self.canned_info


class FakeOllamaClient:
    def __init__(self, canned_response: str = ""):
        self.canned_response = canned_response
        self.calls: list[tuple[str, str]] = []

    def generate(self, model: str, prompt: str) -> str:
        self.calls.append((model, prompt))
        return self.canned_response


@pytest.fixture
def fake_command_runner() -> FakeCommandRunner:
    return FakeCommandRunner()


@pytest.fixture
def fake_sync_command_runner() -> FakeSyncCommandRunner:
    return FakeSyncCommandRunner()
