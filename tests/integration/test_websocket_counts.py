import asyncio
import json
import pytest
from starlette.testclient import TestClient


@pytest.fixture()
def sync_client():
    """Synchronous TestClient for WebSocket tests."""
    from backend.main import app
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


# ── WebSocket connection tests ────────────────────────────────────────────


def test_websocket_connects_and_accepts(sync_client):
    """WebSocket connection to /ws/counts is accepted without immediate close."""
    with sync_client.websocket_connect("/ws/counts?profile_id=test-connect-id") as ws:
        # If we reach here, the connection was accepted successfully.
        # The endpoint does not close immediately; it waits for events.
        assert ws is not None


def test_websocket_receives_event(sync_client):
    """
    After subscribing, putting an event into the CountingService queue
    causes the WebSocket to forward it as a JSON message.
    """
    from backend.services.counting_service import get_or_create_service

    profile_id = "test-ws-event-profile"

    with sync_client.websocket_connect(f"/ws/counts?profile_id={profile_id}") as ws:
        # Get the service that the WS handler subscribed to
        svc = get_or_create_service(profile_id)

        # Directly emit an event into all subscribed queues via _emit_event.
        # _emit_event is synchronous and uses put_nowait, so it works from a
        # sync context as long as there is an event loop running the queue.
        svc._emit_event("in", 1)

        # Receive the message forwarded by the WebSocket handler
        raw = ws.receive_text()
        data = json.loads(raw)

        assert data["direction"] == "in"
        assert data["occupancy"] == 1
        assert "timestamp" in data


def test_websocket_multiple_events(sync_client):
    """Multiple events are forwarded in order."""
    from backend.services.counting_service import get_or_create_service

    profile_id = "test-ws-multi-profile"

    with sync_client.websocket_connect(f"/ws/counts?profile_id={profile_id}") as ws:
        svc = get_or_create_service(profile_id)

        svc._emit_event("in", 1)
        svc._emit_event("out", 0)

        msg1 = json.loads(ws.receive_text())
        msg2 = json.loads(ws.receive_text())

        assert msg1["direction"] == "in"
        assert msg1["occupancy"] == 1
        assert msg2["direction"] == "out"
        assert msg2["occupancy"] == 0


def test_websocket_different_profiles_isolated(sync_client):
    """Events for profile A do not appear on a connection for profile B."""
    from backend.services.counting_service import get_or_create_service

    profile_a = "test-ws-isolation-a"
    profile_b = "test-ws-isolation-b"

    with sync_client.websocket_connect(f"/ws/counts?profile_id={profile_b}") as ws_b:
        # Emit an event for profile A — should NOT reach ws_b
        svc_a = get_or_create_service(profile_a)
        svc_a._emit_event("in", 99)

        # Emit an event for profile B — should reach ws_b
        svc_b = get_or_create_service(profile_b)
        svc_b._emit_event("in", 1)

        msg = json.loads(ws_b.receive_text())
        # We should receive the profile-B event, not profile-A's occupancy=99
        assert msg["occupancy"] == 1
        assert msg["direction"] == "in"
