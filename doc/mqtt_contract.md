# MQTT Contract

## 1. Namespace

Все MQTT topics в рамках контракта используют namespace:

`home/iot/v1`

Полный topic всегда начинается с этого префикса.

## 2. Topic List

| Topic | Назначение |
| --- | --- |
| `home/iot/v1/discovery/<device_id>` | описание устройства и его capabilities |
| `home/iot/v1/device/<device_id>/availability` | доступность устройства |
| `home/iot/v1/device/<device_id>/telemetry` | поток измерений |
| `home/iot/v1/device/<device_id>/state` | последнее известное состояние |
| `home/iot/v1/device/<device_id>/command` | команда устройству |
| `home/iot/v1/device/<device_id>/command_ack` | результат обработки команды |
| `home/iot/v1/device/<device_id>/error` | ошибка на стороне устройства или адаптера |

## 3. Идентификаторы

Имена topics и идентификаторы должны быть безопасны для MQTT и логирования.

Рекомендуемый формат `device_id`:

`[a-z0-9][a-z0-9_-]{1,63}`

Разрешённые символы:

- латинские буквы в нижнем регистре;
- цифры;
- символы `-` и `_`;
- разделитель `/` только как разделитель уровней topic.

Запрещены пробелы, управляющие символы и произвольные спецсимволы.

## 4. Retain и QoS Policy

| Topic | Direction | Retain | QoS | Purpose |
| --- | --- | --- | --- | --- |
| `home/iot/v1/discovery/<device_id>` | device/adapter -> broker -> backend | yes | 1 | metadata and capabilities |
| `home/iot/v1/device/<device_id>/availability` | device/adapter -> broker -> backend | yes | 1 | online/offline/sleeping/degraded |
| `home/iot/v1/device/<device_id>/telemetry` | device/adapter -> broker -> backend | no | 0/1 | time-series measurements |
| `home/iot/v1/device/<device_id>/state` | device/adapter -> broker -> backend/UI bridge | yes | 1 | latest full state |
| `home/iot/v1/device/<device_id>/command` | backend -> broker -> device/adapter | no | 1 | command request |
| `home/iot/v1/device/<device_id>/command_ack` | device/adapter -> broker -> backend | no | 1 | command result |
| `home/iot/v1/device/<device_id>/error` | device/adapter -> broker -> backend | no | 1 | device-side error event |

Retained messages используются только для данных, которые описывают текущее или последнее известное состояние: discovery, availability и state.

Telemetry, command, command_ack и error не должны быть retained. Эти сообщения представляют события, которые не должны автоматически переигрываться новым подписчикам или устройствам после переподключения.

## 5. Discovery Message

Discovery message описывает устройство, источник интеграции и набор поддерживаемых capabilities. Сообщение является registry/metadata event и не должно использоваться как telemetry или state.

Topic:

`home/iot/v1/discovery/<device_id>`

Retain/QoS:

- retain: `true`
- qos: `1`

Payload:

```json
{
  "schema_version": 1,
  "device_id": "lab-mqtt-01",
  "name": "Lab MQTT Device 01",
  "manufacturer": "DIY",
  "model": "pc-emulator-v1",
  "firmware_version": "0.1.0",
  "protocol": "mqtt",
  "transport": "tcp",
  "integration": {
    "type": "mqtt",
    "source": "direct"
  },
  "room": "cabinet",
  "read_only": true,
  "controllable": false,
  "capabilities": [
    {
      "id": "temperature",
      "type": "sensor.temperature",
      "direction": "ro",
      "unit": "°C",
      "value_type": "number"
    },
    {
      "id": "humidity",
      "type": "sensor.humidity",
      "direction": "ro",
      "unit": "%",
      "value_type": "number"
    },
    {
      "id": "voltage",
      "type": "meter.voltage",
      "direction": "ro",
      "unit": "V",
      "value_type": "number"
    },
    {
      "id": "power",
      "type": "meter.power",
      "direction": "ro",
      "unit": "W",
      "value_type": "number"
    },
    {
      "id": "device_status",
      "type": "device.status",
      "direction": "ro",
      "value_type": "string"
    }
  ],
  "created_at": "2026-05-20T14:00:00Z"
}
```

Capability содержит два разных идентификатора:

- `id` — локальное имя параметра в payload конкретного устройства;
- `type` — канонический semantic type внутри системы.

Пример:

```json
{
  "id": "temperature",
  "type": "sensor.temperature"
}
```

В telemetry payload ключом будет `temperature`, а внутри системы значение может быть обработано как `sensor.temperature`.

Для устройств других производителей локальное имя может отличаться:

| Payload field | Canonical type |
| --- | --- |
| `temperature` | `sensor.temperature` |
| `current_temperature` | `sensor.temperature` |
| `relative_humidity` | `sensor.humidity` |

Такой подход отделяет device/vendor-specific naming от внутренней модели capabilities.

## 6. Availability Message

Availability message описывает текущую доступность устройства.

Topic:

`home/iot/v1/device/<device_id>/availability`

Retain/QoS:

- retain: `true`
- qos: `1`

Payload:

```json
{
  "schema_version": 1,
  "device_id": "lab-mqtt-01",
  "ts": "2026-05-20T14:01:00Z",
  "status": "online",
  "reason": "connected"
}
```

Допустимые значения `status` для MVP:

- `online`
- `offline`
- `unknown`
- `sleeping`
- `degraded`

Для первого MQTT-эмулятора достаточно поддержать:

- `online`
- `offline`

Типовые сценарии публикации:

| Сценарий | Payload fragment |
| --- | --- |
| Устройство подключилось | `{ "status": "online", "reason": "connected" }` |
| Аварийное отключение, broker публикует LWT | `{ "status": "offline", "reason": "lwt" }` |
| Штатное отключение перед MQTT disconnect | `{ "status": "offline", "reason": "graceful_disconnect" }` |

## 7. Telemetry Message

Telemetry message представляет событие измерения и используется для time-series данных.

Topic:

`home/iot/v1/device/<device_id>/telemetry`

Retain/QoS:

- retain: `false`
- qos: `0` или `1`

Для MVP рекомендуется QoS 1, чтобы упростить наблюдение доставки. Для частой telemetry допускается переход на QoS 0.

Payload:

```json
{
  "schema_version": 1,
  "device_id": "lab-mqtt-01",
  "ts": "2026-05-20T14:02:00Z",
  "seq": 42,
  "measurements": {
    "temperature": 23.42,
    "humidity": 45.8,
    "voltage": 229.7,
    "power": 12.4,
  }
}
```

Правила:

- `ts` содержит время измерения в UTC.
- `seq` содержит монотонный счётчик сообщений от устройства и используется для диагностики потерь или дубликатов.
- `measurements` содержит словарь значений.
- Ключи `measurements` должны соответствовать capability `id` из discovery.

Если telemetry содержит ключ, отсутствующий в discovery, MVP worker должен:

- записать известные metrics;
- залогировать warning для неизвестного metric;
- не завершать обработку с фатальной ошибкой.

## 10. State Message

State message содержит последнее полное состояние устройства.

Topic:

`home/iot/v1/device/<device_id>/state`

Retain/QoS:

- retain: `true`
- qos: `1`

Для MVP устройство может не публиковать state напрямую. Backend может вычислять current state из telemetry. Topic фиксируется в контракте для последующего расширения.

Payload:

```json
{
  "schema_version": 1,
  "device_id": "lab-mqtt-01",
  "ts": "2026-05-20T14:02:00Z",
  "state": {
    "temperature": 23.42,
    "humidity": 45.8,
    "voltage": 229.7,
    "power": 12.4,
    "device_status": "online"
  }
}
```

Telemetry и state имеют разную семантику:

| Message | Семантика |
| --- | --- |
| telemetry | событие измерения: в указанное время было получено значение |
| state | последнее известное состояние устройства |

Для простых устройств payload telemetry и state может быть похожим, но их назначение различается.

## 11. Command Message

Command message используется backend-ом для отправки команды устройству или адаптеру.

Topic:

`home/iot/v1/device/<device_id>/command`

Retain/QoS:

- retain: `false`
- qos: `1`

Command messages не должны быть retained. Retained command может быть доставлена устройству после переподключения и привести к повторному выполнению устаревшего действия.

Payload:

```json
{
  "schema_version": 1,
  "command_id": "6e59e4bb-ff4d-4b50-a8dc-cdff8e8adf04",
  "device_id": "lab-mqtt-01",
  "ts": "2026-05-20T14:03:00Z",
  "capability": "switch.on_off",
  "command": "set",
  "params": {
    "value": true
  },
  "requested_by": "web-ui"
}
```

## 12. Command ACK Message

Command ACK message сообщает результат обработки команды.

Topic:

`home/iot/v1/device/<device_id>/command_ack`

Retain/QoS:

- retain: `false`
- qos: `1`

Payload success:

```json
{
  "schema_version": 1,
  "command_id": "6e59e4bb-ff4d-4b50-a8dc-cdff8e8adf04",
  "device_id": "lab-mqtt-01",
  "ts": "2026-05-20T14:03:01Z",
  "status": "accepted",
  "result": {
    "applied": true
  }
}
```

Payload failure:

```json
{
  "schema_version": 1,
  "command_id": "6e59e4bb-ff4d-4b50-a8dc-cdff8e8adf04",
  "device_id": "lab-mqtt-01",
  "ts": "2026-05-20T14:03:01Z",
  "status": "rejected",
  "error": {
    "code": "unsupported_capability",
    "message": "Capability switch.on_off is not supported"
  }
}
```

Допустимые статусы для MVP:

- `accepted`
- `rejected`
- `failed`

Зарезервированные статусы для будущих версий:

- `queued`
- `in_progress`
- `timeout`

## 13. Error Message

Error message сообщает об ошибке на стороне устройства или адаптера.

Topic:

`home/iot/v1/device/<device_id>/error`

Retain/QoS:

- retain: `false`
- qos: `1`

Payload:

```json
{
  "schema_version": 1,
  "device_id": "lab-mqtt-01",
  "ts": "2026-05-20T14:04:00Z",
  "severity": "warning",
  "error": {
    "code": "sensor_read_failed",
    "message": "Failed to read voltage sensor"
  },
  "context": {
    "sensor": "voltage"
  }
}
```

Error topic не обязателен для первой реализации MVP, но зарезервирован контрактом.

## 14. Общие поля Payload

Рекомендуемые общие поля:

| Field | Назначение |
| --- | --- |
| `schema_version` | версия JSON-схемы payload |
| `device_id` | идентификатор устройства |
| `ts` | timestamp события или измерения |

`device_id` указывается и в topic, и в payload. Это упрощает логирование, сохранение raw payload, валидацию и перенос payload через другие транспорты.

Worker должен проверять соответствие:

`device_id` из topic == `device_id` из payload

Несовпадение считается ошибкой контракта.

## 15. Timestamp Rules

Для MVP используется следующий формат времени:

| Параметр | Значение |
| --- | --- |
| формат | ISO 8601 |
| timezone | UTC |
| пример | `2026-05-20T14:02:00Z` |

UTC используется для хранения и передачи данных. Локальное время применяется только на frontend при отображении.

## 16. Value Types

Поддерживаемые типы значений:

- `number`
- `string`
- `boolean`
- `enum`
- `object`

Рекомендуемое отображение value types на поля хранения:

| Value type | Storage field |
| --- | --- |
| `number` | `value_num DOUBLE PRECISION` |
| `string` | `value_text TEXT` |
| `boolean` | `value_bool BOOLEAN` |
| `enum` | `value_text TEXT` |
| `object` | `value_json JSONB` |

Минимальный набор для MVP:

- `value_num`
- `value_text`

## 17. Capability Taxonomy

Canonical capability types для MVP:

| Type | Назначение |
| --- | --- |
| `sensor.temperature` | температура |
| `sensor.humidity` | влажность |
| `sensor.battery` | заряд батареи |
| `meter.voltage` | напряжение |
| `meter.current` | ток |
| `meter.power` | мощность |
| `meter.energy` | энергия |
| `switch.on_off` | бинарный выключатель |
| `humidifier.on_off` | включение/выключение увлажнителя |
| `humidifier.target_humidity` | целевая влажность |
| `humidifier.mode` | режим работы |
| `humidifier.water_level` | уровень воды |
| `humidifier.fan_speed` | скорость вентилятора |
| `device.status` | статус устройства |
| `device.availability` | доступность устройства |

Capabilities тестового MQTT-устройства:

- `sensor.temperature`
- `sensor.humidity`
- `meter.voltage`
- `meter.power`
- `device.status`

Capabilities Xiaomi humidifier:

- `sensor.humidity`
- `sensor.temperature`, если доступно
- `humidifier.on_off`
- `humidifier.target_humidity`
- `humidifier.mode`
- `humidifier.water_level`
- `device.status`

Capabilities Яндекс-розетки:

- `switch.on_off`
- `meter.power`, если доступно
- `meter.voltage`, если доступно
- `meter.current`, если доступно
- `device.status`

## 18. Topic Routing

Универсальный worker подписывается на:

`home/iot/v1/#`

Маршрутизация выполняется по topic pattern:

| Topic pattern | Handler |
| --- | --- |
| `home/iot/v1/discovery/<device_id>` | `handle_discovery` |
| `home/iot/v1/device/<device_id>/availability` | `handle_availability` |
| `home/iot/v1/device/<device_id>/telemetry` | `handle_telemetry` |
| `home/iot/v1/device/<device_id>/state` | `handle_state` |
| `home/iot/v1/device/<device_id>/command_ack` | `handle_command_ack` |
| `home/iot/v1/device/<device_id>/error` | `handle_device_error` |

Backend command publisher отправляет команды в:

`home/iot/v1/device/<device_id>/command`

## 19. Validation Rules

Worker должен выполнять минимальную валидацию:

- topic соответствует известному pattern;
- payload является валидным JSON;
- `schema_version` поддерживается;
- `device_id` из topic совпадает с `device_id` из payload;
- `ts` присутствует или заменяется на `server_received_at`;
- telemetry содержит `measurements`;
- ключи `measurements` известны из discovery;
- тип значения соответствует capability `value_type`;
- command разрешена для capability с `direction=rw`;
- read-only устройство не принимает command.

Для MVP используется soft validation:

- ошибка логируется;
- worker продолжает обработку следующих сообщений;
- bad messages не записываются в `measurement_raw`;
- unknown fields сохраняются в metadata или raw payload.

## 20. Idempotency и дубликаты

QoS 1 допускает повторную доставку MQTT-сообщений. Обработчики должны учитывать возможные дубликаты.

Для MVP telemetry messages принимаются без обязательной дедупликации. Поле `seq` используется для диагностики.

В следующих версиях допускается добавить опциональное поле `message_id`:

```json
{
  "schema_version": 1,
  "message_id": "0f2e7265-e040-4bd4-90aa-9dc81c443f76",
  "device_id": "lab-mqtt-01",
  "ts": "2026-05-20T14:02:00Z",
  "seq": 42,
  "measurements": {
    "temperature": 23.42
  }
}
```

Если `message_id` присутствует, backend может использовать его для дедупликации. Если `message_id` отсутствует, сообщение принимается как новое.

Уникальность только по `device_id + seq` или `device_id + ts + metric` не является универсальной, потому что `seq` может сбрасываться после перезапуска, а несколько readings могут иметь одинаковый timestamp.

## 21. Unknown Device Policy

Если telemetry получена от устройства, которое отсутствует в registry, например:

`home/iot/v1/device/unknown-01/telemetry`

MVP policy:

- залогировать warning;
- не записывать telemetry;
- не создавать устройство автоматически.

Автоматическое создание placeholder device и quarantine/dead-letter flow могут быть добавлены в следующих версиях.

## 22. Unknown Metric Policy

Если telemetry содержит metric, отсутствующий в discovery, например:

```json
{
  "measurements": {
    "temperature": 23.5,
    "co2": 700
  }
}
```

MVP policy:

- записать известные metrics;
- залогировать warning для неизвестных metrics;
- не создавать dynamic capability автоматически;
- не прерывать обработку всего сообщения из-за одного неизвестного metric.

## 23. Security Considerations

MQTT payload считается внешним вводом даже в локальной сети.

Минимальные ограничения:

- ограничивать размер payload;
- ограничивать длину `device_id`;
- ограничивать длину metric id;
- запрещать неожиданные topic levels;
- валидировать JSON;
- проверять capability перед исполнением command;
- не хранить секреты в MQTT payload.

Планируемые меры:

- Mosquitto auth;
- ACL по topics;
- отдельные credentials для устройств;
- TLS;
- изолированная VLAN/IoT network.

## 24. Итоговая таблица контракта

| Topic | Direction | Retain | QoS | Purpose |
| --- | --- | --- | --- | --- |
| `home/iot/v1/discovery/<device_id>` | device/adapter -> broker -> backend | yes | 1 | metadata and capabilities |
| `home/iot/v1/device/<device_id>/availability` | device/adapter -> broker -> backend | yes | 1 | online/offline/sleeping/degraded |
| `home/iot/v1/device/<device_id>/telemetry` | device/adapter -> broker -> backend | no | 0/1 | time-series measurements |
| `home/iot/v1/device/<device_id>/state` | device/adapter -> broker -> backend/UI bridge | yes | 1 | latest full state |
| `home/iot/v1/device/<device_id>/command` | backend -> broker -> device/adapter | no | 1 | command request |
| `home/iot/v1/device/<device_id>/command_ack` | device/adapter -> broker -> backend | no | 1 | command result |
| `home/iot/v1/device/<device_id>/error` | device/adapter -> broker -> backend | no | 1 | device-side error event |
