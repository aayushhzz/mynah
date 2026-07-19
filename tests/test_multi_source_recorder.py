from __future__ import annotations

import threading
from pathlib import Path

import pytest

from recording.background import NoActiveRecordingError, RecordingAlreadyActiveError
from recording.multi_source import (
    MultiSourceRecorder,
    NoSourcesStartedError,
    SourceSpec,
)
from recording.recorder import EmptyRecordingError


class FakeMultiLauncher:
    def __init__(self, fail_names=None, skip_write_names=None, start_pid=1000):
        self.launched_cmds: list[list[str]] = []
        self._next_pid = start_pid
        self.fail_names = fail_names or set()
        self.skip_write_names = skip_write_names or set()

    def launch(self, cmd: list[str]) -> int:
        self.launched_cmds.append(cmd)
        output_path = Path(cmd[-1])
        name = output_path.stem
        if name in self.fail_names:
            raise OSError(f"boom for {name}")
        pid = self._next_pid
        self._next_pid += 1
        if name not in self.skip_write_names:
            output_path.write_bytes(b"RIFF....WAVEfmt ")
        return pid


class FakeProcessController:
    def __init__(self, alive_pids: set[int] | None = None):
        self.alive_pids = alive_pids if alive_pids is not None else set()
        self.terminated_pids: list[int] = []
        self.killed_pids: list[int] = []

    def is_alive(self, pid: int) -> bool:
        return pid in self.alive_pids

    def terminate(self, pid: int) -> None:
        self.terminated_pids.append(pid)
        self.alive_pids.discard(pid)

    def kill(self, pid: int) -> None:
        self.killed_pids.append(pid)
        self.alive_pids.discard(pid)


def _cmd_builder(label: str):
    return lambda output_path: [label, str(output_path)]


def _two_sources():
    return [
        SourceSpec(name="mic", build_cmd=_cmd_builder("mic-binary")),
        SourceSpec(name="system_audio", build_cmd=_cmd_builder("sys-binary")),
    ]


def test_start_launches_all_sources_and_saves_state(tmp_path):
    launcher = FakeMultiLauncher()
    controller = FakeProcessController()
    from recording.background import RecordingStateStore

    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources())

    warnings = recorder.start(tmp_path / "sources", title="Standup")

    assert warnings == []
    assert len(launcher.launched_cmds) == 2
    assert launcher.launched_cmds[0][-1] == str(tmp_path / "sources" / "mic.wav")
    assert launcher.launched_cmds[1][-1] == str(tmp_path / "sources" / "system_audio.wav")


def test_start_twice_raises_already_active(tmp_path):
    from recording.background import RecordingStateStore

    launcher = FakeMultiLauncher()
    controller = FakeProcessController()
    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources())

    recorder.start(tmp_path / "sources", title="Standup")

    with pytest.raises(RecordingAlreadyActiveError):
        recorder.start(tmp_path / "sources2", title="Other")


def test_start_continues_when_one_source_fails_to_launch(tmp_path):
    from recording.background import RecordingStateStore

    launcher = FakeMultiLauncher(fail_names={"system_audio"})
    controller = FakeProcessController()
    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources())

    warnings = recorder.start(tmp_path / "sources", title="Standup")

    assert len(warnings) == 1
    assert "system_audio" in warnings[0]

    state = store.load()
    assert len(state.sources) == 1
    assert state.sources[0].name == "mic"


def test_start_raises_when_all_sources_fail_to_launch(tmp_path):
    from recording.background import RecordingStateStore

    launcher = FakeMultiLauncher(fail_names={"mic", "system_audio"})
    controller = FakeProcessController()
    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources())

    with pytest.raises(NoSourcesStartedError):
        recorder.start(tmp_path / "sources", title="Standup")

    assert not store.exists()


def test_is_recording_true_if_any_source_alive(tmp_path):
    from recording.background import RecordingStateStore

    launcher = FakeMultiLauncher(start_pid=100)
    controller = FakeProcessController(alive_pids={100})
    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources())

    assert recorder.is_recording() is False

    recorder.start(tmp_path / "sources")
    assert recorder.is_recording() is True

    controller.alive_pids.clear()
    assert recorder.is_recording() is False


def test_is_recording_false_and_self_heals_when_state_file_corrupt(tmp_path):
    from recording.background import RecordingStateStore

    state_path = tmp_path / "state.json"
    state_path.write_text("not valid json{{{")
    store = RecordingStateStore(state_path)
    recorder = MultiSourceRecorder(FakeMultiLauncher(), FakeProcessController(), store, _two_sources())

    assert recorder.is_recording() is False
    assert not store.exists()


def test_stop_returns_all_valid_sources_and_title(tmp_path):
    from recording.background import RecordingStateStore

    launcher = FakeMultiLauncher(start_pid=200)
    controller = FakeProcessController(alive_pids={200, 201})
    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources(), poll_interval=0)

    recorder.start(tmp_path / "sources", title="Retro")
    sources, title, warnings = recorder.stop()

    assert title == "Retro"
    assert warnings == []
    names = {name for name, _ in sources}
    assert names == {"mic", "system_audio"}
    for _, path in sources:
        assert path.exists()
    assert 200 in controller.terminated_pids
    assert 201 in controller.terminated_pids
    assert not store.exists()


def test_stop_drops_source_with_empty_output_but_keeps_others(tmp_path):
    from recording.background import RecordingStateStore

    launcher = FakeMultiLauncher(skip_write_names={"system_audio"}, start_pid=300)
    controller = FakeProcessController(alive_pids={300, 301})
    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources(), poll_interval=0)

    recorder.start(tmp_path / "sources")
    sources, _, warnings = recorder.stop()

    names = {name for name, _ in sources}
    assert names == {"mic"}
    assert len(warnings) == 1
    assert "system_audio" in warnings[0]


def test_stop_raises_empty_recording_error_if_all_sources_invalid(tmp_path):
    from recording.background import RecordingStateStore

    launcher = FakeMultiLauncher(skip_write_names={"mic", "system_audio"}, start_pid=400)
    controller = FakeProcessController(alive_pids=set())
    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources())

    recorder.start(tmp_path / "sources")

    with pytest.raises(EmptyRecordingError):
        recorder.stop()

    assert not store.exists()


def test_stop_without_active_recording_raises(tmp_path):
    from recording.background import RecordingStateStore

    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(FakeMultiLauncher(), FakeProcessController(), store, _two_sources())

    with pytest.raises(NoActiveRecordingError):
        recorder.stop()


def test_concurrent_start_calls_only_one_wins(tmp_path):
    from recording.background import RecordingStateStore

    launcher = FakeMultiLauncher(start_pid=600)
    controller = FakeProcessController()
    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources())

    results: list[str] = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(8)

    def attempt(idx):
        barrier.wait()
        try:
            recorder.start(tmp_path / f"sources-{idx}", title=f"Racer-{idx}")
            outcome = "started"
        except RecordingAlreadyActiveError:
            outcome = "rejected"
        with results_lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("started") == 1
    assert results.count("rejected") == 7

    state = store.load()
    assert len(state.sources) == 2


def test_multi_source_integration(tmp_path):
    from recording.background import RecordingStateStore

    launcher = FakeMultiLauncher(start_pid=500)
    controller = FakeProcessController(alive_pids={500, 501})
    store = RecordingStateStore(tmp_path / "state.json")
    recorder = MultiSourceRecorder(launcher, controller, store, _two_sources(), poll_interval=0)

    assert recorder.is_recording() is False

    warnings = recorder.start(tmp_path / "sources", title="Kickoff")
    assert warnings == []
    assert recorder.is_recording() is True

    sources, title, stop_warnings = recorder.stop()

    assert title == "Kickoff"
    assert stop_warnings == []
    assert len(sources) == 2
    assert recorder.is_recording() is False
