from __future__ import annotations

from pathlib import Path

import pytest

from common.process import CompletedProcess
from recording.mixer import AudioMixingError, build_mix_cmd, mix_audio


class FakeMixingRunner:
    def __init__(self, returncode: int = 0, write_output: bool = True, stderr: str = "boom"):
        self.returncode = returncode
        self.write_output = write_output
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def run(self, cmd: list[str], input: str | None = None) -> CompletedProcess:
        self.calls.append(cmd)
        if self.write_output:
            Path(cmd[-1]).write_bytes(b"RIFF....WAVEfmt ")
        return CompletedProcess(
            returncode=self.returncode,
            stdout="",
            stderr="" if self.returncode == 0 else self.stderr,
        )


def test_build_mix_cmd_single_input_uses_loudnorm_without_amix(tmp_path):
    input_path = tmp_path / "mic.wav"
    output_path = tmp_path / "out.wav"

    cmd = build_mix_cmd("ffmpeg", [input_path], output_path)

    assert cmd == [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-af",
        "loudnorm",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]


def test_build_mix_cmd_two_inputs_normalizes_and_mixes(tmp_path):
    mic_path = tmp_path / "mic.wav"
    system_path = tmp_path / "system.wav"
    output_path = tmp_path / "out.wav"

    cmd = build_mix_cmd("ffmpeg", [mic_path, system_path], output_path)

    assert cmd == [
        "ffmpeg",
        "-y",
        "-i",
        str(mic_path),
        "-i",
        str(system_path),
        "-filter_complex",
        (
            "[0:a]loudnorm,aresample=16000,aformat=channel_layouts=mono[a0];"
            "[1:a]loudnorm,aresample=16000,aformat=channel_layouts=mono[a1];"
            "[a0][a1]amix=inputs=2:duration=longest:normalize=0[aout]"
        ),
        "-map",
        "[aout]",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]


def test_build_mix_cmd_three_inputs_generalizes(tmp_path):
    paths = [tmp_path / "a.wav", tmp_path / "b.wav", tmp_path / "c.wav"]
    output_path = tmp_path / "out.wav"

    cmd = build_mix_cmd("ffmpeg", paths, output_path)

    assert "[0:a]loudnorm,aresample=16000,aformat=channel_layouts=mono[a0]" in cmd[cmd.index("-filter_complex") + 1]
    assert "[1:a]loudnorm,aresample=16000,aformat=channel_layouts=mono[a1]" in cmd[cmd.index("-filter_complex") + 1]
    assert "[2:a]loudnorm,aresample=16000,aformat=channel_layouts=mono[a2]" in cmd[cmd.index("-filter_complex") + 1]
    assert "[a0][a1][a2]amix=inputs=3:duration=longest:normalize=0[aout]" in cmd[cmd.index("-filter_complex") + 1]


def test_mix_audio_raises_with_no_inputs(tmp_path):
    runner = FakeMixingRunner()

    with pytest.raises(AudioMixingError):
        mix_audio(runner, [], tmp_path / "out.wav")


def test_mix_audio_success_returns_output_path(tmp_path):
    runner = FakeMixingRunner()
    input_path = tmp_path / "mic.wav"
    input_path.write_bytes(b"fake")
    output_path = tmp_path / "out.wav"

    result = mix_audio(runner, [input_path], output_path)

    assert result == output_path
    assert output_path.exists()
    assert runner.calls[0][0] == "ffmpeg"


def test_mix_audio_raises_on_nonzero_exit(tmp_path):
    runner = FakeMixingRunner(returncode=1, write_output=False, stderr="filter error")
    input_path = tmp_path / "mic.wav"
    input_path.write_bytes(b"fake")

    with pytest.raises(AudioMixingError):
        mix_audio(runner, [input_path], tmp_path / "out.wav")


def test_mix_audio_raises_when_output_missing(tmp_path):
    runner = FakeMixingRunner(write_output=False)
    input_path = tmp_path / "mic.wav"
    input_path.write_bytes(b"fake")

    with pytest.raises(AudioMixingError):
        mix_audio(runner, [input_path], tmp_path / "out.wav")


def test_mixer_integration_two_sources(tmp_path):
    runner = FakeMixingRunner()
    mic_path = tmp_path / "mic.wav"
    system_path = tmp_path / "system.wav"
    mic_path.write_bytes(b"fake-mic")
    system_path.write_bytes(b"fake-system")
    output_path = tmp_path / "mixed.wav"

    result = mix_audio(runner, [mic_path, system_path], output_path)

    assert result == output_path
    assert output_path.exists()
    built_cmd = runner.calls[0]
    assert str(mic_path) in built_cmd
    assert str(system_path) in built_cmd
    assert "amix=inputs=2" in built_cmd[built_cmd.index("-filter_complex") + 1]
