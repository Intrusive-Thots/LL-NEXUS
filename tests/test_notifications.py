from nexus.core.events.bus import EventBus
from nexus.services.notifications.service import NotificationService, NotifyLevel, Notification


def test_notification_service_levels():
    bus = EventBus()
    svc = NotificationService(bus)

    received = []
    bus.subscribe("notify", lambda evt: received.append(evt))

    svc.info("Info Title", "Info Body")
    svc.success("Success Title")
    svc.warning("Warning Title")
    svc.critical("Critical Title")

    assert len(received) == 4
    assert received[0].payload["title"] == "Info Title"
    assert received[0].payload["level"] == "info"

    assert received[1].payload["title"] == "Success Title"
    assert received[1].payload["level"] == "success"

    assert received[2].payload["title"] == "Warning Title"
    assert received[2].payload["level"] == "warning"

    assert received[3].payload["title"] == "Critical Title"
    assert received[3].payload["level"] == "critical"


def test_notification_service_disabled():
    bus = EventBus()
    svc = NotificationService(bus, enabled=False)

    received = []
    bus.subscribe("notify", lambda evt: received.append(evt))

    svc.info("Should Not Publish")
    assert len(received) == 0


def test_notification_custom_payload():
    bus = EventBus()
    svc = NotificationService(bus)

    received = []
    bus.subscribe("notify", lambda evt: received.append(evt))

    svc.notify(Notification(
        title="Custom",
        body="Body",
        level=NotifyLevel.WARNING,
        duration_ms=10000,
        action_label="Undo"
    ))

    assert len(received) == 1
    assert received[0].payload["duration_ms"] == 10000
    assert received[0].payload["action_label"] == "Undo"
