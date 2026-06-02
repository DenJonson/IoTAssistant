from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from psycopg import Connection

from app.db import get_connection
from app.ingestion.writer import write_device, write_measurement
from app.integrations.home_assistant.client import HomeAssistantWebSocketClient
from app.integrations.home_assistant.mapper import (
    normalized_device_from_ha_registry_state,
    normalized_measurement_from_ha_registry_state,
)


async def load_registry_indexes(
    *,
    client,
    websocket,
) -> tuple[dict[str, dict], dict[str, dict]]:
    entity_registry = await client.get_entity_registry(websocket)
    device_registry = await client.get_device_registry(websocket)

    entity_registry_by_entity_id = build_entity_registry_index(entity_registry)
    device_registry_by_device_id = build_device_registry_index(device_registry)

    print(
        f"home_assistant.registry.loaded "
        f"entities={len(entity_registry_by_entity_id)} "
        f"devices={len(device_registry_by_device_id)}",
        flush=True,
    )

    return entity_registry_by_entity_id, device_registry_by_device_id


def has_registry_context_for_state(
    *,
    state: dict,
    entity_registry_by_entity_id: dict[str, dict],
    device_registry_by_device_id: dict[str, dict],
) -> bool:
    entity_id = state.get("entity_id")

    if not isinstance(entity_id, str):
        return False

    entity_entry = entity_registry_by_entity_id.get(entity_id)

    if entity_entry is None:
        return False

    device_id = entity_entry.get("device_id")

    if not isinstance(device_id, str):
        return False

    return device_id in device_registry_by_device_id


def build_entity_registry_index(
    entity_registry: list[dict],
) -> dict[str, dict]:
    result: dict[str, dict] = {}

    for entity in entity_registry:
        entity_id = entity.get("entity_id")

        if isinstance(entity_id, str):
            result[entity_id] = entity

    return result


def build_device_registry_index(
    device_registry: list[dict],
) -> dict[str, dict]:
    result: dict[str, dict] = {}

    for device in device_registry:
        device_id = device.get("id")

        if isinstance(device_id, str):
            result[device_id] = device

    return result


def resolve_registry_context(
    *,
    state: dict,
    entity_registry_by_entity_id: dict[str, dict],
    device_registry_by_device_id: dict[str, dict],
) -> tuple[dict | None, dict | None]:
    entity_id = state.get("entity_id")

    if not isinstance(entity_id, str):
        return None, None

    entity_entry = entity_registry_by_entity_id.get(entity_id)

    if entity_entry is None:
        return None, None

    device_id = entity_entry.get("device_id")

    if not isinstance(device_id, str):
        return entity_entry, None

    return entity_entry, device_registry_by_device_id.get(device_id)


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

def get_allowed_domains() -> set[str]:
    raw_value = os.getenv(
        "HOME_ASSISTANT_ALLOWED_DOMAINS",
        "sensor,binary_sensor,light,switch,climate,cover,lock,fan",
    )

    domains = {
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    }

    if not domains:
        raise RuntimeError("HOME_ASSISTANT_ALLOWED_DOMAINS must not be empty")

    return domains


def get_excluded_entity_prefixes() -> tuple[str, ...]:
    raw_value = os.getenv(
        "HOME_ASSISTANT_EXCLUDED_ENTITY_PREFIXES",
        "sensor.backup_,sun.,zone.,person.,conversation.,event.",
    )

    return tuple(
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    )


def should_ingest_state(
    state: dict,
    *,
    allowed_domains: set[str],
    excluded_entity_prefixes: tuple[str, ...],
) -> bool:
    entity_id = state.get("entity_id")

    if not isinstance(entity_id, str):
        return False

    if any(entity_id.startswith(prefix) for prefix in excluded_entity_prefixes):
        return False

    if "." not in entity_id:
        return False

    domain = entity_id.split(".", 1)[0]

    return domain in allowed_domains


def ingest_ha_state(
    conn: Connection,
    *,
    state: dict,
    server_received_at: datetime,
    entity_registry_by_entity_id: dict[str, dict],
    device_registry_by_device_id: dict[str, dict],
) -> bool:
    entity_entry, device_entry = resolve_registry_context(
        state=state,
        entity_registry_by_entity_id=entity_registry_by_entity_id,
        device_registry_by_device_id=device_registry_by_device_id,
    )

    device = normalized_device_from_ha_registry_state(
        state,
        entity_entry=entity_entry,
        device_entry=device_entry,
    )

    write_device(
        conn=conn,
        device=device,
    )

    measurement = normalized_measurement_from_ha_registry_state(
        state,
        entity_entry=entity_entry,
        device_entry=device_entry,
        server_received_at=server_received_at,
    )

    if measurement is None:
        return False

    write_measurement(
        conn=conn,
        measurement=measurement,
    )

    return True


def ingest_snapshot(
    *,
    states: list[dict],
    sync_limit: int,
    allowed_domains: set[str],
    excluded_entity_prefixes: tuple[str, ...],
    entity_registry_by_entity_id: dict[str, dict],
    device_registry_by_device_id: dict[str, dict],
) -> int:
    ingested_count = 0
    server_received_at = datetime.now(timezone.utc)

    with get_connection() as conn:
        for state in states[:sync_limit]:
            if not should_ingest_state(
                state,
                allowed_domains=allowed_domains,
                excluded_entity_prefixes=excluded_entity_prefixes,
            ):
                continue

            did_write_measurement = ingest_ha_state(
                conn=conn,
                state=state,
                server_received_at=server_received_at,
                entity_registry_by_entity_id=entity_registry_by_entity_id,
                device_registry_by_device_id=device_registry_by_device_id,
            )

            if did_write_measurement:
                ingested_count += 1

        conn.commit()

    return ingested_count


def ingest_live_state_change(
    *,
    state: dict,
    entity_registry_by_entity_id: dict[str, dict],
    device_registry_by_device_id: dict[str, dict],
) -> bool:
    server_received_at = datetime.now(timezone.utc)

    with get_connection() as conn:
        did_write_measurement = ingest_ha_state(
            conn=conn,
            state=state,
            server_received_at=server_received_at,
            entity_registry_by_entity_id=entity_registry_by_entity_id,
            device_registry_by_device_id=device_registry_by_device_id,
        )
        conn.commit()

    return did_write_measurement


async def run_worker() -> None:
    base_url = get_required_env("HOME_ASSISTANT_URL")
    access_token = get_required_env("HOME_ASSISTANT_TOKEN")
    sync_limit = get_sync_limit()
    allowed_domains = get_allowed_domains()
    excluded_entity_prefixes = get_excluded_entity_prefixes()

    print(
        f"home_assistant.worker.config sync_limit={sync_limit} \n"
        f"allowed_domains={sorted(allowed_domains)} \n"
        f"excluded_entity_prefixes={list(excluded_entity_prefixes)}\n",
        flush=True,
    )

    client = HomeAssistantWebSocketClient(
        base_url=base_url,
        access_token=access_token,
    )

    while True:
        try:
            websocket = await client.connect()

            print("home_assistant.websocket.connected", flush=True)

            states = await client.get_states(websocket)

            entity_registry_by_entity_id, device_registry_by_device_id = await load_registry_indexes(
                client=client,
                websocket=websocket,
            )

            print(
                f"home_assistant.registry.loaded "
                f"entities={len(entity_registry_by_entity_id)} "
                f"devices={len(device_registry_by_device_id)}",
                flush=True,
            )
            
            ingested_count = ingest_snapshot(
                states=states,
                sync_limit=sync_limit,
                allowed_domains=allowed_domains,
                excluded_entity_prefixes=excluded_entity_prefixes,
                entity_registry_by_entity_id=entity_registry_by_entity_id,
                device_registry_by_device_id=device_registry_by_device_id,
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
                if not should_ingest_state(
                    state,
                    allowed_domains=allowed_domains,
                    excluded_entity_prefixes=excluded_entity_prefixes,
                ):
                    continue

                if not has_registry_context_for_state(
                    state=state,
                    entity_registry_by_entity_id=entity_registry_by_entity_id,
                    device_registry_by_device_id=device_registry_by_device_id,
                ):
                    print(
                        f"home_assistant.registry.refresh_requested entity_id={state.get('entity_id')}",
                        flush=True,
                    )

                    entity_registry_by_entity_id, device_registry_by_device_id = await load_registry_indexes(
                        client=client,
                        websocket=websocket,
                    )

                did_write_measurement = ingest_live_state_change(
                    state=state,
                    entity_registry_by_entity_id=entity_registry_by_entity_id,
                    device_registry_by_device_id=device_registry_by_device_id,
                )

                if did_write_measurement:
                    print(
                        f"home_assistant.state_changed.ingested entity_id={state.get('entity_id')}",
                        flush=True,
                    )
                else:
                    print(
                        f"home_assistant.state_changed.device_only entity_id={state.get('entity_id')}",
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