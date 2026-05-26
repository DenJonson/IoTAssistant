# IoTAssistant API

## Назначение

API — это read-only HTTP-слой между frontend-ом и PostgreSQL.

Frontend не подключается к БД напрямую. Он делает HTTP-запросы к API и получает JSON.

Текущая схема:

```text
Browser / Frontend
        ↓ HTTP
API service
        ↓ SQL
PostgreSQL
```

API скрывает внутреннюю структуру БД:

```text
device.id                         не отдаём наружу
device.external_device_id          отдаём как device_id
value_num/value_text/value_bool    отдаём как единое поле value
```

---

# Base URL

Локально:

```text
http://localhost:8000
```

Внутри Docker Compose network:

```text
http://api:8000
```

---

# Endpoints

## GET `/api/health`

Проверка, что API service запущен и отвечает.

### Request

```http
GET /api/health
```

### Example

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

### Response

```json
{
  "status": "ok"
}
```

---

## GET `/api/devices`

Возвращает список известных устройств.

### Request

```http
GET /api/devices
```

### Example

```powershell
Invoke-RestMethod http://localhost:8000/api/devices
```

### Response

```json
[
  {
    "device_id": "lab-mqtt-01",
    "name": "Lab MQTT Device 01",
    "manufacturer": "Lab",
    "model": "MQTT emulator",
    "protocol": "mqtt",
    "transport": "mqtt",
    "room": "lab",
    "read_only": true,
    "controllable": false,
    "last_seen_at": "2026-05-26T13:50:00Z"
  }
]
```

### Fields

| Field | Type | Description |
|---|---:|---|
| `device_id` | string | Public device identifier. Comes from `device.external_device_id`. |
| `name` | string | Human-readable device name. |
| `manufacturer` | string | Device manufacturer. |
| `model` | string/null | Device model. |
| `protocol` | string | Integration protocol, for example `mqtt`. |
| `transport` | string/null | Transport, for example `mqtt`, `wifi`, `ble`. |
| `room` | string/null | Logical room/location. |
| `read_only` | boolean | Whether the device is read-only. |
| `controllable` | boolean | Whether commands may be supported later. |
| `last_seen_at` | string/null | Last backend-observed activity timestamp. |

---

## GET `/api/devices/{device_id}/state`

Возвращает текущее состояние устройства из `device_state_current`.

Это snapshot последних известных значений, а не история измерений.

### Request

```http
GET /api/devices/{device_id}/state
```

### Example

```powershell
Invoke-RestMethod http://localhost:8000/api/devices/lab-mqtt-01/state
```

### Response

```json
{
  "device_id": "lab-mqtt-01",
  "state": [
    {
      "capability_id": "availability",
      "capability_type": "device.availability",
      "value_type": "string",
      "unit": null,
      "value": "online",
      "event_ts": "2026-05-26T13:50:00Z",
      "server_received_at": "2026-05-26T13:50:01Z"
    },
    {
      "capability_id": "temperature",
      "capability_type": "sensor.temperature",
      "value_type": "number",
      "unit": "°C",
      "value": 23.4,
      "event_ts": "2026-05-26T13:50:00Z",
      "server_received_at": "2026-05-26T13:50:01Z"
    }
  ]
}
```

### Fields

| Field | Type | Description |
|---|---:|---|
| `device_id` | string | Public device identifier. |
| `state` | array | Current state items. |
| `state[].capability_id` | string | Local capability id, for example `temperature`. |
| `state[].capability_type` | string/null | Semantic capability type, for example `sensor.temperature`. |
| `state[].value_type` | string/null | Declared value type: `number`, `string`, `boolean`. |
| `state[].unit` | string/null | Unit, for example `°C`, `%`, `W`. |
| `state[].value` | number/string/boolean/null | Current value. |
| `state[].event_ts` | string | Timestamp from the original device event. |
| `state[].server_received_at` | string | Timestamp when backend received/processed the event. |

### Unknown device

If the device does not exist:

```http
HTTP/1.1 404 Not Found
```

```json
{
  "detail": "Device not found"
}
```

---

## GET `/api/devices/{device_id}/measurements`

Возвращает историю numeric-измерений для одной capability.

Этот endpoint предназначен для будущих графиков.

Пока API отдаёт только numeric values из:

```text
measurement_raw.value_num
```

Строковые и boolean-значения в этом endpoint-е не возвращаются.

### Request

```http
GET /api/devices/{device_id}/measurements?capability_id={capability_id}&limit={limit}
```

### Query parameters

| Parameter | Required | Type | Default | Description |
|---|---:|---:|---:|---|
| `capability_id` | yes | string | — | Capability to read, for example `temperature`. |
| `limit` | no | integer | `1000` | Maximum number of points. Clamped to range `1..5000`. |

### Example

```powershell
Invoke-RestMethod "http://localhost:8000/api/devices/lab-mqtt-01/measurements?capability_id=temperature&limit=100"
```

### Response

```json
{
  "device_id": "lab-mqtt-01",
  "capability_id": "temperature",
  "unit": "°C",
  "points": [
    {
      "ts": "2026-05-26T13:45:00Z",
      "value": 23.1
    },
    {
      "ts": "2026-05-26T13:46:00Z",
      "value": 23.3
    },
    {
      "ts": "2026-05-26T13:47:00Z",
      "value": 23.4
    }
  ]
}
```

### Fields

| Field | Type | Description |
|---|---:|---|
| `device_id` | string | Public device identifier. |
| `capability_id` | string | Requested capability. |
| `unit` | string/null | Unit of the series, for example `°C`. |
| `points` | array | Measurement points ordered from older to newer. |
| `points[].ts` | string | Measurement timestamp. |
| `points[].value` | number | Numeric measurement value. |

### Unknown device

If the device does not exist:

```http
HTTP/1.1 404 Not Found
```

```json
{
  "detail": "Device not found"
}
```

### Missing `capability_id`

If `capability_id` is not provided:

```http
HTTP/1.1 422 Unprocessable Entity
```

This response is generated by FastAPI because `capability_id` is a required query parameter.

---

# API Design Rules

## Public identifiers

API uses:

```text
device_id = device.external_device_id
```

API does not expose internal PostgreSQL UUIDs by default.

Good:

```text
/api/devices/lab-mqtt-01/state
```

Avoid exposing:

```text
/api/devices/75c2bcb7-7e9b-4b55-9a0d-...
```

---

## Value representation

Database stores scalar values in separate columns:

```text
value_num
value_text
value_bool
```

API exposes one unified field:

```json
{
  "value": 23.4
}
```

or:

```json
{
  "value": "online"
}
```

or:

```json
{
  "value": true
}
```

This keeps SQL storage explicit while keeping API convenient for frontend.

---

## Read-only boundary

Current API is read-only.

Allowed now:

```text
GET /api/health
GET /api/devices
GET /api/devices/{device_id}/state
GET /api/devices/{device_id}/measurements
```

Not implemented yet:

```text
POST /api/devices
POST /api/commands
PUT /api/devices/{device_id}
DELETE /api/devices/{device_id}
```

The API must not publish MQTT commands until the command model, auth model and safety rules are designed.

---

# Current Implementation Structure

```text
backend/app/api/main.py
  FastAPI app, routes, HTTP parameters, HTTP errors

backend/app/api/mappers.py
  DB dict rows -> API JSON shape

backend/app/repository.py
  SQL queries, dict rows

backend/app/db.py
  PostgreSQL connection
```

Dependency direction:

```text
api/main.py
  -> api/mappers.py
  -> repository.py
  -> db.py
```

Repository code should not import FastAPI or API mappers.

---

# Local Diagnostics

## Check API container

```powershell
docker compose ps api
```

## API logs

```powershell
docker compose logs -f api
```

## Health check

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

## List devices

```powershell
Invoke-RestMethod http://localhost:8000/api/devices
```

## Device state

```powershell
Invoke-RestMethod http://localhost:8000/api/devices/lab-mqtt-01/state
```

## Measurements

```powershell
Invoke-RestMethod "http://localhost:8000/api/devices/lab-mqtt-01/measurements?capability_id=temperature&limit=100"
```

## Swagger UI

```text
http://localhost:8000/docs
```

FastAPI automatically exposes interactive API documentation at `/docs`.

## GET `/api/devices/{device_id}/capabilities`

Возвращает список capabilities устройства.

Этот endpoint нужен frontend-у, чтобы понять, какие параметры устройство поддерживает и какие из них можно использовать для графиков.

### Request

```http
GET /api/devices/{device_id}/capabilities
```

### Example

```powershell
Invoke-RestMethod http://localhost:8000/api/devices/lab-mqtt-01/capabilities
```

### Response

```json
{
  "device_id": "lab-mqtt-01",
  "capabilities": [
    {
      "capability_id": "temperature",
      "capability_type": "sensor.temperature",
      "direction": "ro",
      "unit": "°C",
      "value_type": "number",
      "source": "device_discovery",
      "chartable": true
    },
    {
      "capability_id": "availability",
      "capability_type": "device.availability",
      "direction": "ro",
      "unit": null,
      "value_type": "string",
      "source": "backend",
      "chartable": false
    }
  ]
}
```

### Fields

| Field | Type | Description |
|---|---:|---|
| `device_id` | string | Public device identifier. |
| `capabilities` | array | Device capability definitions. |
| `capabilities[].capability_id` | string | Local capability id, for example `temperature`. |
| `capabilities[].capability_type` | string | Semantic type, for example `sensor.temperature`. |
| `capabilities[].direction` | string | Access direction: `ro`, `rw`, `wo`. |
| `capabilities[].unit` | string/null | Unit, for example `°C`, `%`, `W`. |
| `capabilities[].value_type` | string | Declared value type: `number`, `string`, `boolean`. |
| `capabilities[].source` | string | Source of capability definition: `device_discovery`, `backend`, `integration`, `derived`. |
| `capabilities[].chartable` | boolean | Whether the current frontend may draw this capability as a line chart. Currently `true` only for `value_type = number`. |

### Unknown device

If the device does not exist:

```http
HTTP/1.1 404 Not Found
```

```json
{
  "detail": "Device not found"
}
```