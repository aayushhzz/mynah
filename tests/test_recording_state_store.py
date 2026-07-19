from __future__ import annotations

import threading

import pytest

from recording.background import NoActiveRecordingError, RecordingState, RecordingStateStore, SourceState


def test_try_claim_succeeds_when_no_state_exists(tmp_path):
    store = RecordingStateStore(tmp_path / "state.json")

    assert store.try_claim() is True
    assert store.exists()


def test_try_claim_fails_when_state_already_exists(tmp_path):
    store = RecordingStateStore(tmp_path / "state.json")
    store.try_claim()

    assert store.try_claim() is False


def test_try_claim_is_atomic_under_concurrent_callers(tmp_path):
    store = RecordingStateStore(tmp_path / "state.json")
    results: list[bool] = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(16)

    def attempt():
        barrier.wait()
        claimed = store.try_claim()
        with results_lock:
            results.append(claimed)

    threads = [threading.Thread(target=attempt) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 1
    assert results.count(False) == 15


def test_save_after_claim_overwrites_placeholder(tmp_path):
    store = RecordingStateStore(tmp_path / "state.json")
    store.try_claim()

    state = RecordingState(sources=[SourceState(name="mic", pid=1, output_path="/tmp/mic.wav")], title="Standup")
    store.save(state)

    loaded = store.load()
    assert loaded == state


def test_clear_allows_reclaiming(tmp_path):
    store = RecordingStateStore(tmp_path / "state.json")
    store.try_claim()
    store.clear()

    assert store.try_claim() is True


def test_load_with_corrupt_json_raises_no_active_recording_and_self_heals(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("not valid json{{{")
    store = RecordingStateStore(state_path)

    with pytest.raises(NoActiveRecordingError):
        store.load()

    assert not store.exists()


def test_load_with_missing_sources_key_raises_no_active_recording_and_self_heals(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text('{"title": "oops"}')
    store = RecordingStateStore(state_path)

    with pytest.raises(NoActiveRecordingError):
        store.load()

    assert not store.exists()


def test_exists_true_for_corrupt_file_but_try_claim_recovers(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("garbage")
    store = RecordingStateStore(state_path)

    assert store.exists() is True

    with pytest.raises(NoActiveRecordingError):
        store.load()

    assert store.try_claim() is True
