from __future__ import annotations

from typing import Protocol

from common.process import SyncCommandRunner


class OllamaError(Exception):
    pass


class OllamaClient(Protocol):
    def generate(self, model: str, prompt: str) -> str: ...


class SubprocessOllamaClient:
    def __init__(self, runner: SyncCommandRunner):
        self._runner = runner

    def generate(self, model: str, prompt: str) -> str:
        result = self._runner.run(["ollama", "run", model], input=prompt)
        if result.returncode != 0:
            raise OllamaError(f"ollama run failed (exit {result.returncode}): {result.stderr}")
        return result.stdout
