from __future__ import annotations

from pathlib import Path

from common.process import SyncCommandRunner


class AudioMixingError(Exception):
    pass


def build_mix_cmd(ffmpeg_binary: str, input_paths: list[Path], output_path: Path) -> list[str]:
    if not input_paths:
        raise AudioMixingError("At least one input audio file is required to mix")

    cmd = [ffmpeg_binary, "-y"]
    for path in input_paths:
        cmd += ["-i", str(path)]

    if len(input_paths) == 1:
        cmd += ["-af", "loudnorm"]
    else:
        labels = [f"a{i}" for i in range(len(input_paths))]
        normalize_steps = ";".join(
            f"[{i}:a]loudnorm,aresample=16000,aformat=channel_layouts=mono[{label}]"
            for i, label in enumerate(labels)
        )
        mix_inputs = "".join(f"[{label}]" for label in labels)
        mix_step = f"{mix_inputs}amix=inputs={len(labels)}:duration=longest:normalize=0[aout]"
        cmd += ["-filter_complex", f"{normalize_steps};{mix_step}", "-map", "[aout]"]

    cmd += ["-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(output_path)]
    return cmd


def mix_audio(runner: SyncCommandRunner, input_paths: list[Path], output_path: Path) -> Path:
    cmd = build_mix_cmd("ffmpeg", input_paths, output_path)

    result = runner.run(cmd)
    if result.returncode != 0:
        raise AudioMixingError(f"ffmpeg mixing failed (exit {result.returncode}): {result.stderr}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise AudioMixingError(f"Mixed output is missing or empty: {output_path}")

    return output_path
