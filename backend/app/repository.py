import uuid

def insert_ingestion_event(
    conn,
    *,
    mqtt_topic: str,
    message_type: str | None,
    device_external_id: str | None,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    raw_payload_text: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_event (
                id,
                mqtt_topic,
                message_type,
                device_external_id,
                status,
                error_code,
                error_message,
                raw_payload_text
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                str(uuid.uuid4()),
                mqtt_topic,
                message_type,
                device_external_id,
                status,
                error_code,
                error_message,
                raw_payload_text,
            ),
        )