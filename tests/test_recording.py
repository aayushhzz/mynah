from __future__ import annotations

import pytest

from recording.duration import get_audio_duration
from recording.recorder import (
    AudioRecorder,
    EmptyRecordingError,
    RecorderAlreadyRunningError,
    RecorderNotStartedError,
    RecordingFailedError,
)


def test_start_builds_correct_ffmpeg_argv(fake_command_runner, tmp_path):
    recorder = AudioRecorder(fake_command_runner, ffmpeg_binary="ffmpeg", input_device=":0")
    output_path = tmp_path / "out.wav"

    recorder.start(output_path)

    assert fake_command_runner.started_cmds == [
        [
            "ffmpeg",
            "-y",
            "-f",
            "avfoundation",
            "-i",
            ":0",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
    ]


def test_stop_returns_path_when_file_exists(fake_command_runner, tmp_path):
    recorder = AudioRecorder(fake_command_runner)
    output_path = tmp_path / "out.wav"

    recorder.start(output_path)
    result = recorder.stop()

    assert result == output_path
    assert output_path.exists()


def test_stop_before_start_raises(fake_command_runner):
    recorder = AudioRecorder(fake_command_runner)

    with pytest.raises(RecorderNotStartedError):
        recorder.stop()


def test_double_start_raises(fake_command_runner, tmp_path):
    recorder = AudioRecorder(fake_command_runner)
    recorder.start(tmp_path / "out1.wav")

    with pytest.raises(RecorderAlreadyRunningError):
        recorder.start(tmp_path / "out2.wav")


def test_missing_output_raises_empty_recording_error(tmp_path):
    from conftest import FakeCommandRunner

    runner = FakeCommandRunner(write_file_on_start=False)
    recorder = AudioRecorder(runner)
    output_path = tmp_path / "out.wav"

    recorder.start(output_path)

    with pytest.raises(EmptyRecordingError):
        recorder.stop()


def test_zero_byte_output_raises_empty_recording_error(tmp_path):
    from conftest import FakeCommandRunner

    runner = FakeCommandRunner(write_file_on_start=True, file_content=b"")
    recorder = AudioRecorder(runner)
    output_path = tmp_path / "out.wav"

    recorder.start(output_path)

    with pytest.raises(EmptyRecordingError):
        recorder.stop()


def test_crashed_process_before_stop_raises_recording_failed_error(fake_command_runner, tmp_path):
    recorder = AudioRecorder(fake_command_runner)
    output_path = tmp_path / "out.wav"

    recorder.start(output_path)
    fake_command_runner.handle.poll_returncode = 1

    with pytest.raises(RecordingFailedError):
        recorder.stop()


def test_is_recording_state(fake_command_runner, tmp_path):
    recorder = AudioRecorder(fake_command_runner)
    output_path = tmp_path / "out.wav"

    assert recorder.is_recording() is False
    recorder.start(output_path)
    assert recorder.is_recording() is True
    recorder.stop()
    assert recorder.is_recording() is False


def test_get_audio_duration_parses_ffprobe_stdout(fake_sync_command_runner):
    fake_sync_command_runner.stdout = "12.345\n"
    duration = get_audio_duration(fake_sync_command_runner, "some.wav")
    assert duration == 12.345


def test_get_audio_duration_raises_on_non_numeric_output(fake_sync_command_runner):
    fake_sync_command_runner.stdout = "not-a-number\n"
    with pytest.raises(ValueError):
        get_audio_duration(fake_sync_command_runner, "some.wav")


def test_recording_integration(fake_command_runner, tmp_path):
    recorder = AudioRecorder(fake_command_runner)
    output_path = tmp_path / "out.wav"

    recorder.start(output_path)
    assert recorder.is_recording() is True

    result = recorder.stop()

    assert result == output_path
    assert output_path.exists()
    assert recorder.is_recording() is False
    assert fake_command_runner.started_cmds[0][-1] == str(output_path)
