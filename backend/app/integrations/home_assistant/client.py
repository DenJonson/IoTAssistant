from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import websockets


class HomeAssistantWebSocketClient:
    def __init__(
        self,
        *,
        base_url: str,
        access_token: str,
        receive_timeout_seconds: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._receive_timeout_seconds = receive_timeout_seconds
        self._next_id = 1

    def websocket_url(self) -> str:
        if self._base_url.startswith("http://"):
            return self._base_url.replace("http://", "ws://", 1) + "/api/websocket"

        if self._base_url.startswith("https://"):
            return self._base_url.replace("https://", "wss://", 1) + "/api/websocket"

        raise ValueError(f"Unsupported Home Assistant URL: {self._base_url}")

    def next_message_id(self) -> int:
        message_id = self._next_id
        self._next_id += 1
        return message_id

    async def connect(self) -> websockets.ClientConnection:
        websocket = await websockets.connect(
            self.websocket_url(),
            ping_interval=30,
            ping_timeout=20,
            close_timeout=10,
        )

        auth_required = json.loads(await websocket.recv())
        if auth_required.get("type") != "auth_required":
            await websocket.close()
            raise RuntimeError(f"Expected auth_required, got: {auth_required}")

        await websocket.send(
            json.dumps(
                {
                    "type": "auth",
                    "access_token": self._access_token,
                }
            )
        )

        auth_response = json.loads(await websocket.recv())

        if auth_response.get("type") == "auth_invalid":
            await websocket.close()
            raise RuntimeError(f"Home Assistant authentication failed: {auth_response}")

        if auth_response.get("type") != "auth_ok":
            await websocket.close()
            raise RuntimeError(f"Expected auth_ok, got: {auth_response}")

        return websocket

    async def get_states(
        self,
        websocket: websockets.ClientConnection,
    ) -> list[dict[str, Any]]:
        message_id = self.next_message_id()

        await websocket.send(
            json.dumps(
                {
                    "id": message_id,
                    "type": "get_states",
                }
            )
        )

        while True:
            message = json.loads(await websocket.recv())

            if message.get("id") != message_id:
                continue

            if message.get("type") != "result":
                raise RuntimeError(f"Expected result for get_states, got: {message}")

            if not message.get("success"):
                raise RuntimeError(f"get_states failed: {message}")

            result = message.get("result")
            if not isinstance(result, list):
                raise RuntimeError(f"get_states returned non-list result: {message}")

            return result

    async def subscribe_state_changed(
        self,
        websocket: websockets.ClientConnection,
    ) -> int:
        message_id = self.next_message_id()

        await websocket.send(
            json.dumps(
                {
                    "id": message_id,
                    "type": "subscribe_events",
                    "event_type": "state_changed",
                }
            )
        )

        while True:
            message = json.loads(await websocket.recv())

            if message.get("id") != message_id:
                continue

            if message.get("type") != "result":
                raise RuntimeError(f"Expected result for subscribe_events, got: {message}")

            if not message.get("success"):
                raise RuntimeError(f"subscribe_events failed: {message}")

            return message_id

    async def state_changed_events(
        self,
        websocket: websockets.ClientConnection,
        *,
        subscription_id: int,
    ) -> AsyncIterator[dict[str, Any]]:
        while True:
            try:
                raw_message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=self._receive_timeout_seconds,
                )
            except TimeoutError:
                ping_id = self.next_message_id()
                await websocket.send(
                    json.dumps(
                        {
                            "id": ping_id,
                            "type": "ping",
                        }
                    )
                )
                continue

            message = json.loads(raw_message)

            if message.get("type") != "event":
                continue

            if message.get("id") != subscription_id:
                continue

            event = message.get("event") or {}
            data = event.get("data") or {}
            new_state = data.get("new_state")

            if isinstance(new_state, dict):
                yield new_state