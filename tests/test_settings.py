from pathlib import Path

from config import settings


def test_settings_have_expected_types():
    assert isinstance(settings.MEETINGS_ROOT, Path)
    assert isinstance(settings.DB_PATH, Path)
    assert isinstance(settings.RECORDING_STATE_PATH, Path)
    assert isinstance(settings.RECORDING_SOURCES_ROOT, Path)
    assert isinstance(settings.SYSTEM_AUDIO_RECORDER_BINARY, Path)
    assert isinstance(settings.WHISPER_MODEL_SIZE, str)
    assert isinstance(settings.OLLAMA_MODEL, str)
