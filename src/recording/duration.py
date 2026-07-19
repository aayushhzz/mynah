from __future__ import annotations

from common.process import SyncCommandRunner


def get_audio_duration(runner: SyncCommandRunner, audio_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = runner.run(cmd)
    return float(result.stdout.strip())
