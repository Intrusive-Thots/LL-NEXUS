import time
from pathlib import Path
from nexus.core.events.bus import EventBus
from nexus.core.sessions.models import Session, SessionEvent
from nexus.core.sessions.recorder import SessionRecorder
from nexus.services.persistence.store import PersistenceService

def test_session_models_serialization():
    ev = SessionEvent(ts=time.time(), kind="state", text="CHAMP_SELECT")
    s = Session(number=1, started_ts=time.time(), queue_type="Ranked", role="ADC", events=[ev])
    d = s.to_dict()
    restored = Session.from_dict(d)
    assert restored.number == 1
    assert restored.queue_type == "Ranked"
    assert len(restored.events) == 1
    assert restored.events[0].kind == "state"

def test_session_recorder_and_persistence(tmp_path: Path):
    bus = EventBus()
    persistence = PersistenceService(tmp_path)
    saved_sessions = []
    recorder = SessionRecorder(bus, on_session_closed=lambda s: (saved_sessions.append(s), persistence.save_session(s)))

    recorder.note_automation("Auto Accept", decision={"kind": "auto_accept"})
    recorder.record_lock("Ahri", decision={"kind": "auto_pick"})
    recorder.close_active(result="WON")

    assert len(saved_sessions) == 1
    assert saved_sessions[0].result == "WON"

    loaded = persistence.load_recent()
    assert len(loaded) == 1
    assert loaded[0].result == "WON"
    persistence.close()
