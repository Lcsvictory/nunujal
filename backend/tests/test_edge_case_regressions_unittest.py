import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import HTTPException
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.api.routes import chats, contribution


@contextmanager
def patched(target, name: str, value):
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)


class DummySession:
    def close(self) -> None:
        pass


class DummyRequest:
    async def is_disconnected(self) -> bool:
        return False


class DummySubscriber:
    def get(self, *_args, **_kwargs):
        raise contribution.QueueEmpty


class DummyWebSocket:
    def __init__(self) -> None:
        self.cookies = {"access_token": "revocable-access-token"}
        self.headers = {}
        self.query_params = {}
        self.application_state = WebSocketState.CONNECTED
        self.close_code: int | None = None
        self.receive_count = 0

    async def accept(self) -> None:
        self.application_state = WebSocketState.CONNECTED

    async def send_json(self, _payload: dict[str, object]) -> None:
        pass

    async def receive_text(self) -> str:
        self.receive_count += 1
        if self.receive_count == 1:
            return "client-still-connected"
        raise WebSocketDisconnect()

    async def close(self, code: int = 1000) -> None:
        self.close_code = code
        self.application_state = WebSocketState.DISCONNECTED


class RealtimeSessionRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_websocket_closes_when_session_is_revoked_after_connect(self):
        auth_calls = 0

        def fake_get_authenticated_user_from_token(_session, _token):
            nonlocal auth_calls
            auth_calls += 1
            if auth_calls == 1:
                return SimpleNamespace(id=7)
            raise HTTPException(status_code=401, detail="Session has expired or was revoked.")

        websocket = DummyWebSocket()
        with patched(chats, "get_session", lambda: DummySession()):
            with patched(chats, "get_authenticated_user_from_token", fake_get_authenticated_user_from_token):
                await chats.chat_events(websocket)

        self.assertGreaterEqual(auth_calls, 2)
        self.assertEqual(websocket.close_code, 4401)

    async def test_contribution_sse_revalidates_session_during_heartbeat(self):
        auth_calls = 0

        def fake_get_authenticated_user(_session, _request, _authorization):
            nonlocal auth_calls
            auth_calls += 1
            if auth_calls == 1:
                return SimpleNamespace(id=7)
            raise HTTPException(status_code=401, detail="Session has expired or was revoked.")

        def fake_load_payload(_project_id, _user_id):
            return {
                "analysis": None,
                "active_analysis": None,
                "open_reviews": [],
                "recent_reviews": [],
                "has_my_pending_assessment": False,
            }

        with patched(contribution, "get_session", lambda: DummySession()):
            with patched(contribution, "get_authenticated_user", fake_get_authenticated_user):
                with patched(contribution, "_require_project_access", lambda _session, project_id, _user_id: (SimpleNamespace(id=project_id), SimpleNamespace())):
                    with patched(contribution, "_load_latest_contribution_payload_for_user", fake_load_payload):
                        with patched(contribution.contribution_assessment_queue, "subscribe", lambda _project_id: DummySubscriber()):
                            with patched(contribution.contribution_assessment_queue, "unsubscribe", lambda _project_id, _subscriber: None):
                                response = await contribution.stream_contribution_events(1, DummyRequest())
                                body_iterator = response.body_iterator
                                first_chunk = await anext(body_iterator)
                                second_chunk = await anext(body_iterator)

        self.assertIn("snapshot", first_chunk)
        self.assertIn("contribution_error", second_chunk)
        self.assertGreaterEqual(auth_calls, 2)


if __name__ == "__main__":
    unittest.main()
