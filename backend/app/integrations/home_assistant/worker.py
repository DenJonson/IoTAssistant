from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from psycopg import Connection

from app.db import get_connection
from app.ingestion.writer import write_device, write_measurement
from app.integrations.home_assistant.client import HomeAssistantWebSocketClient
from app.integrations.home_assistant.mapper import (
    normalized_device_from_ha_state,
    normalized_measurement_from_ha_state,
)


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value.strip()


def get_sync_limit() -> int:
    raw_value = os.getenv("HOME_ASSISTANT_SYNC_LIMIT", "500")

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"HOME_ASSISTANT_SYNC_LIMIT must be an integer, got: {raw_value}"
        ) from exc

    if value <= 0:
        raise RuntimeError("HOME_ASSISTANT_SYNC_LIMIT must be greater than zero")

    return value


def should_ingest_state(state: dict) -> bool:
    entity_id = state.get("entity_id")

    if not isinstance(entity_id, str):
        return False

    if "." not in entity_id:
        return False

    return True


def ingest_ha_state(
    conn: Connection,
    *,
    state: dict,
    server_received_at: datetime,
) -> None:
    device = normalized_device_from_ha_state(state)
    measurement = normalized_measurement_from_ha_state(
        state,
        server_received_at=server_received_at,
    )

    write_device(conn=conn, device=device)
    write_measurement(conn=conn, measurement=measurement)


def ingest_snapshot(
    *,
    states: list[dict],
    sync_limit: int,
) -> int:
    ingested_count = 0
    server_received_at = datetime.now(timezone.utc)

    with get_connection() as conn:
        for state in states[:sync_limit]:
            if not should_ingest_state(state):
                continue

            ingest_ha_state(
                conn=conn,
                state=state,
                server_received_at=server_received_at,
            )
            ingested_count += 1

        conn.commit()

    return ingested_count


def ingest_live_state_change(
    *,
    state: dict,
) -> None:
    server_received_at = datetime.now(timezone.utc)

    with get_connection() as conn:
        ingest_ha_state(
            conn=conn,
            state=state,
            server_received_at=server_received_at,
        )
        conn.commit()


async def run_worker() -> None:
    base_url = get_required_env("HOME_ASSISTANT_URL")
    access_token = get_required_env("HOME_ASSISTANT_TOKEN")
    sync_limit = get_sync_limit()

    client = HomeAssistantWebSocketClient(
        base_url=base_url,
        access_token=access_token,
    )

    while True:
        try:
            websocket = await client.connect()

            print("home_assistant.websocket.connected", flush=True)

            states = await client.get_states(websocket)
            ingested_count = ingest_snapshot(
                states=states,
                sync_limit=sync_limit,
            )

            print(
                f"home_assistant.snapshot.ingested count={ingested_count}",
                flush=True,
            )

            subscription_id = await client.subscribe_state_changed(websocket)

            print(
                f"home_assistant.state_changed.subscribed id={subscription_id}",
                flush=True,
            )

            async for state in client.state_changed_events(
                websocket,
                subscription_id=subscription_id,
            ):
                if not should_ingest_state(state):
                    continue

                ingest_live_state_change(state=state)

                print(
                    f"home_assistant.state_changed.ingested entity_id={state.get('entity_id')}",
                    flush=True,
                )

        except Exception as exc:
            print(
                f"home_assistant.worker.error error={type(exc).__name__}: {exc}",
                flush=True,
            )
            await asyncio.sleep(10)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()