from __future__ import annotations

from pathlib import Path

from common.process import CommandRunner, ProcessHandle


class RecorderAlreadyRunningError(Exception):
    pass


class RecorderNotStartedError(Exception):
    pass


class RecordingFailedError(Exception):
    pass


class EmptyRecordingError(Exception):
    pass


def build_ffmpeg_record_cmd(ffmpeg_binary: str, input_device: str, output_path: Path) -> list[str]:
    return [
        ffmpeg_binary,
        "-y",
        "-f",
        "avfoundation",
        "-i",
        input_device,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]


class AudioRecorder:
    def __init__(
        self,
        command_runner: CommandRunner,
        ffmpeg_binary: str = "ffmpeg",
        input_device: str = ":0",
    ):
        self._command_runner = command_runner
        self._ffmpeg_binary = ffmpeg_binary
        self._input_device = input_device
        self._handle: ProcessHandle | None = None
        self._output_path: Path | None = None

    def start(self, output_path: Path) -> None:
        if self._handle is not None:
            raise RecorderAlreadyRunningError("Recording already in progress")

        cmd = build_ffmpeg_record_cmd(self._ffmpeg_binary, self._input_device, output_path)
        self._handle = self._command_runner.start(cmd)
        self._output_path = output_path

    def stop(self) -> Path:
        if self._handle is None:
            raise RecorderNotStartedError("Recording was never started")

        crashed = self._handle.poll() is not None
        self._handle.terminate()
        self._handle.wait()

        handle_was_crashed = crashed
        output_path = self._output_path
        self._handle = None
        self._output_path = None

        if handle_was_crashed:
            raise RecordingFailedError("Recording process crashed before stop() was called")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise EmptyRecordingError(f"Recording output is missing or empty: {output_path}")

        return output_path

    def is_recording(self) -> bool:
        return self._handle is not None
