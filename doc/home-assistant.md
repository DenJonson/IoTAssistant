# Интеграция с Home Assistant

## Назначение

Home Assistant используется как внешний integration adapter для устройств, которые управляются или обнаруживаются через Home Assistant.

Наш проект при этом сохраняет собственную canonical model устройств и пишет нормализованные данные в PostgreSQL.

Общий поток данных:

```text
Home Assistant
  -> WebSocket API
  -> ha_worker
  -> canonical ingestion writer
  -> PostgreSQL
  -> API/UI
```

## Текущий проверенный сценарий

На текущем этапе проверен сценарий с MQTT-эмулятором:

```text
MQTT emulator
  -> Mosquitto
  -> Home Assistant MQTT device discovery
  -> Home Assistant device/entity registry
  -> Home Assistant WebSocket state_changed
  -> ha_worker
  -> PostgreSQL
```

Результат:

```text
HA device registry entry -> device
HA entity registry entry -> device_capability
HA state                 -> measurement_raw + device_state_current
```

## Docker service

Home Assistant запускается как сервис Docker Compose.

Для Windows + Docker Desktop в dev-режиме используется host networking:

```yaml
homeassistant:
  image: ghcr.io/home-assistant/home-assistant:stable
  restart: unless-stopped
  network_mode: host
  volumes:
    - ./data/homeassistant/config:/config
  environment:
    TZ: ${TZ:-Europe/Moscow}
```

UI Home Assistant доступен здесь:

```text
http://localhost:8123
```

Конфигурация Home Assistant хранится в bind mount:

```text
data/homeassistant/config/
```

Эту директорию не нужно коммитить в Git.

## Переменные окружения

Для сервисов внутри Docker Compose, которые подключаются к Home Assistant:

```env
HOME_ASSISTANT_URL=http://host.docker.internal:8123
HOME_ASSISTANT_TOKEN=<long-lived-access-token>
HOME_ASSISTANT_SYNC_LIMIT=500

HOME_ASSISTANT_ALLOWED_DOMAINS=sensor,binary_sensor,light,switch,climate,cover,lock,fan
HOME_ASSISTANT_EXCLUDED_ENTITY_PREFIXES=sensor.backup_,sensor.sun_,sun.,zone.,person.,conversation.,event.
```

Для браузера:

```text
http://localhost:8123
```

Для контейнеров Docker Compose:

```text
http://host.docker.internal:8123
```

## Long-Lived Access Token

Токен создаётся в Home Assistant:

```text
Profile -> Security -> Long-Lived Access Tokens -> Create Token
```

Рекомендуемое имя токена:

```text
IoTAssistant dev integration
```

Токен хранится только в `.env`.

Не нужно вставлять реальный токен в `docker-compose.yml`, README или документацию.

## Подключение MQTT broker в Home Assistant

В UI Home Assistant:

```text
Settings -> Devices & services -> Add integration -> MQTT
```

Параметры broker:

```text
Broker: localhost
Port: 1883
Username: пусто
Password: пусто
```

Это работает потому, что Home Assistant запущен в `network_mode: host`, а Mosquitto опубликован на host-порту `1883`.

Если в другой среде `localhost` не работает, нужно проверить сетевую схему Docker/host и адрес broker.

## MQTT Discovery в Home Assistant

Для устройств с несколькими параметрами используется **Home Assistant MQTT device discovery**.

Правильный discovery topic:

```text
homeassistant/device/<device_object_id>/config
```

Пример:

```text
homeassistant/device/lab_mqtt_01_ha/config
```

Важно: для device discovery в topic должен быть компонент `device`.

Правильно:

```text
homeassistant/device/lab_mqtt_01_ha/config
```

Неправильно для device discovery:

```text
homeassistant/sensor/lab_mqtt_01_ha/config
```

Topic `homeassistant/sensor/.../config` используется для single component discovery, то есть для одной entity/sensor, а не для устройства с несколькими components.

## Пример device discovery payload

```json
{
  "dev": {
    "ids": "lab-mqtt-01-ha",
    "name": "Lab MQTT 01",
    "mf": "IoTAssistant Emulator",
    "mdl": "MQTT Lab Device",
    "sw": "0.1.0",
    "sn": "lab-mqtt-01-ha",
    "hw": "pc-emulator"
  },
  "o": {
    "name": "iotassistant-emulator",
    "sw": "0.1.0",
    "url": "https://example.local/iotassistant"
  },
  "cmps": {
    "temperature": {
      "p": "sensor",
      "name": "Temperature Sensor",
      "unique_id": "lab-mqtt-01-ha-temperature",
      "device_class": "temperature",
      "state_class": "measurement",
      "unit_of_measurement": "°C",
      "value_template": "{{ value_json.temperature }}"
    },
    "humidity": {
      "p": "sensor",
      "name": "Humidity Sensor",
      "unique_id": "lab-mqtt-01-ha-humidity",
      "device_class": "humidity",
      "state_class": "measurement",
      "unit_of_measurement": "%",
      "value_template": "{{ value_json.humidity }}"
    },
    "voltage": {
      "p": "sensor",
      "name": "Voltage Sensor",
      "unique_id": "lab-mqtt-01-ha-voltage",
      "device_class": "voltage",
      "state_class": "measurement",
      "unit_of_measurement": "V",
      "value_template": "{{ value_json.voltage }}"
    },
    "power": {
      "p": "sensor",
      "name": "Power Sensor",
      "unique_id": "lab-mqtt-01-ha-power",
      "device_class": "power",
      "state_class": "measurement",
      "unit_of_measurement": "W",
      "value_template": "{{ value_json.power }}"
    },
    "device_status": {
      "p": "sensor",
      "name": "Device Status",
      "unique_id": "lab-mqtt-01-ha-device-status",
      "value_template": "{{ value_json.device_status }}"
    }
  },
  "state_topic": "homeassistant/lab-mqtt-01-ha/state",
  "qos": 1
}
```

## Пример state payload

State topic:

```text
homeassistant/lab-mqtt-01-ha/state
```

Payload:

```json
{
  "temperature": 22.14,
  "humidity": 45.2,
  "voltage": 229.7,
  "power": 12.4,
  "device_status": "running"
}
```

## Важные правила MQTT Discovery

### `dev` описывает устройство

```json
"dev": {
  "ids": "lab-mqtt-01-ha",
  "name": "Lab MQTT 01"
}
```

Это попадёт в Home Assistant Device Registry как одно устройство.

В нашем backend это маппится в `device`.

Пример:

```text
device.external_device_id = ha:device:mqtt:lab-mqtt-01-ha
device.name               = Lab MQTT 01
device.protocol           = home_assistant
device.transport          = websocket
```

### `cmps` описывает компоненты устройства

Каждый элемент `cmps` становится отдельной Home Assistant entity.

В нашем backend каждая такая entity маппится в `device_capability`.

Пример temperature capability:

```text
capability_id      = lab-mqtt-01-ha-temperature
capability_type    = home_assistant.sensor.temperature
direction          = ro
unit               = °C
value_type         = number
source             = integration
```

### `unique_id` должен быть у каждого component

`unique_id` относится к entity/component, а не к устройству.

Правильно:

```text
lab-mqtt-01-ha-temperature
lab-mqtt-01-ha-humidity
lab-mqtt-01-ha-voltage
lab-mqtt-01-ha-power
```

Неправильно использовать один и тот же `unique_id` для всех components:

```text
lab-mqtt-01-ha
```

Если entity не имеет `unique_id`, Home Assistant не сможет нормально управлять ей через UI.

## Mapping в нашем backend

`ha_worker` использует registry-aware mapping.

На старте worker загружает:

```text
config/entity_registry/list
config/device_registry/list
get_states
```

Затем строит индексы:

```text
entity_id -> entity_registry_entry
device_id -> device_registry_entry
```

Mapping:

```text
Home Assistant device registry entry
  -> device

Home Assistant entity registry entry
  -> device_capability

Home Assistant state
  -> measurement_raw
  -> device_state_current
```

Пример результата в таблице `device`:

```text
external_device_id = ha:device:mqtt:lab-mqtt-01-ha
name               = Lab MQTT 01
manufacturer       = IoTAssistant Emulator
model              = MQTT Lab Device
protocol           = home_assistant
transport          = websocket
```

Пример результата в `device_capability`:

```text
capability_id      = lab-mqtt-01-ha-temperature
capability_type    = home_assistant.sensor.temperature
direction          = ro
unit               = °C
value_type         = number
source             = integration
```

Пример результата в `device_state_current`:

```text
external_device_id = ha:device:mqtt:lab-mqtt-01-ha
capability_id      = lab-mqtt-01-ha-temperature
value_num          = 22.14
unit               = °C
```

## Ingestion ownership

Для каждого устройства должен быть ровно один ingestion owner.

### Native MQTT path

```text
protocol="mqtt"
```

Поток:

```text
device/emulator
  -> Mosquitto
  -> mqtt_worker
  -> PostgreSQL
```

### Home Assistant MQTT path

```text
protocol="home_assistant_mqtt"
```

Поток:

```text
device/emulator
  -> Mosquitto
  -> Home Assistant MQTT integration
  -> Home Assistant WebSocket API
  -> ha_worker
  -> PostgreSQL
```

Если устройство идёт через `home_assistant_mqtt`, Home Assistant может также хранить историю в своей Recorder DB. Это нормально: HA Recorder является внутренней историей Home Assistant, а PostgreSQL остаётся canonical storage нашего проекта.

## Debug registry tool

Для диагностики Home Assistant registry есть dev-tool:

```text
app.integrations.home_assistant.debug_registry
```

Запуск:

```powershell
docker compose exec -T -e HOME_ASSISTANT_DEBUG_NEEDLE=lab_mqtt_01 ha_worker python -u -m app.integrations.home_assistant.debug_registry
```

Он печатает три блока:

```text
MATCHED STATES
MATCHED ENTITY REGISTRY ENTRIES
MATCHED DEVICE REGISTRY ENTRIES
```

Этот инструмент полезен, если устройство видно в HA, но неправильно маппится в нашу БД.

## Проверка worker

Логи:

```powershell
docker compose logs -f ha_worker
```

Ожидаемые сообщения:

```text
home_assistant.websocket.connected
home_assistant.registry.loaded entities=... devices=...
home_assistant.snapshot.ingested count=...
home_assistant.state_changed.subscribed id=...
```

## Проверка данных в БД

### Устройства из Home Assistant

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT external_device_id, name, manufacturer, model, protocol, transport, last_seen_at FROM device WHERE protocol = 'home_assistant' ORDER BY updated_at DESC;"
```

### Capabilities

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT d.external_device_id, c.capability_id, c.capability_type, c.direction, c.unit, c.value_type, c.source FROM device_capability c JOIN device d ON d.id = c.device_id WHERE d.protocol = 'home_assistant' ORDER BY d.external_device_id, c.capability_id;"
```

### Current state

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT d.external_device_id, s.capability_id, s.value_num, s.value_text, s.value_bool, s.unit, s.event_ts FROM device_state_current s JOIN device d ON d.id = s.device_id WHERE d.protocol = 'home_assistant' ORDER BY d.external_device_id, s.capability_id;"
```

### Raw measurements

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT d.external_device_id, m.capability_id, m.metric, m.value_num, m.value_text, m.value_bool, m.unit, m.event_ts FROM measurement_raw m JOIN device d ON d.id = m.device_id WHERE d.protocol = 'home_assistant' ORDER BY m.server_received_at DESC LIMIT 30;"
```

## Очистка dev-данных Home Assistant в нашей БД

Если нужно удалить импортированные HA-устройства и прогнать sync заново:

```powershell
docker compose exec db psql -U iot -d iot -c "DELETE FROM device WHERE protocol = 'home_assistant';"
docker compose restart ha_worker
```

Это удаляет только устройства, импортированные через Home Assistant. Native MQTT devices не затрагиваются.

## Очистка неправильных retained MQTT Discovery topics

Если ранее были опубликованы неправильные discovery topics, например через `homeassistant/sensor/.../config` вместо `homeassistant/device/.../config`, их нужно удалить retained empty payload-ом.

Посмотреть discovery topics:

```powershell
docker run --rm --network iotassistant_default eclipse-mosquitto:2.0 mosquitto_sub `
  -h mosquitto `
  -p 1883 `
  -v `
  -t "homeassistant/#" `
  -C 50
```

Удалить неправильный retained topic:

```powershell
docker run --rm --network iotassistant_default eclipse-mosquitto:2.0 mosquitto_pub `
  -h mosquitto `
  -p 1883 `
  -r `
  -n `
  -t "homeassistant/sensor/<old_object_id>/config"
```

Правильный topic для device discovery:

```text
homeassistant/device/<device_object_id>/config
```

## Текущее состояние интеграции

На текущем этапе проверено:

```text
2 HA MQTT emulator devices
  -> Home Assistant
  -> ha_worker
  -> PostgreSQL
```

Устройства корректно появляются:

```text
device
  -> device_capability[]
  -> device_state_current
  -> measurement_raw
```

Все свойства устройства корректно определяются и обновляются.