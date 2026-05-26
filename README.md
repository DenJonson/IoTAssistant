# IoTAssistant Dev Commands

## Основной запуск

Обычный запуск всей dev-среды:

```powershell
docker compose up -d --build
```

Эта команда поднимает основные сервисы:

```text
mosquitto  — MQTT broker
db         — PostgreSQL
worker     — MQTT ingestion worker
adminer    — web-интерфейс к PostgreSQL
migrate    — запускается при создании контейнеров и применяет миграции к БД
```

Если PostgreSQL volume отсутствует, `schema.sql` применяется автоматически через `/docker-entrypoint-initdb.d`.

---

## Полный reset dev-БД

Удалить контейнеры, network и volumes:

```powershell
docker compose down -v
```

Заново поднять стенд:

```powershell
docker compose up -d --build
```

После удаления volume PostgreSQL создаст новую БД и применит:

```text
deploy/db/schema.sql
```

А migrator применит описанные миграции

---

## Запуск эмулятора

Эмулятор запускается на host-машине, поэтому подключается к опубликованному MQTT-порту:

```powershell
python -u .\emulator\mqtt_emulator.py
```

---

## Adminer

URL:

```text
http://localhost:8081
```

Параметры подключения:

```text
System:   PostgreSQL
Server:   db
Username: iot
Password: iot_dev_password
Database: iot
```

`Server = db`, потому что Adminer работает внутри Docker Compose network.

---

# Диагностика Docker Compose

## Посмотреть состояние сервисов

```powershell
docker compose ps
```

С учётом остановленных/созданных контейнеров:

```powershell
docker compose ps -a
```

Ожидаемые основные состояния:

```text
db          Up ... healthy
mosquitto   Up ... healthy
worker      Up
adminer     Up
```

---

## Посмотреть итоговую Compose-конфигурацию

```powershell
docker compose config
```

Список сервисов:

```powershell
docker compose config --services
```

Полезно, если сервис не появляется в `docker compose ps`.

---

## Логи всех сервисов

```powershell
docker compose logs -f
```

## Логи worker-а

```powershell
docker compose logs -f worker
```

Последние 100 строк:

```powershell
docker compose logs --tail=100 worker
```

## Логи PostgreSQL

```powershell
docker compose logs -f db
```

## Логи Mosquitto

```powershell
docker compose logs -f mosquitto
```

---

## Перезапуск отдельного сервиса

```powershell
docker compose restart worker
```

```powershell
docker compose restart db
```

```powershell
docker compose restart mosquitto
```

---

## Пересборка worker-а

Если менялся Python-код worker-а или `backend/requirements.txt`:

```powershell
docker compose up -d --build worker
```

Если менялся Dockerfile или несколько сервисов:

```powershell
docker compose up -d --build
```

---

# Диагностика PostgreSQL

## Открыть psql внутри контейнера

```powershell
docker compose exec db psql -U iot -d iot
```

Выход из `psql`:

```sql
\q
```

---

## Проверить список таблиц

```powershell
docker compose exec db psql -U iot -d iot -c "\dt"
```

---

## Проверить структуру таблицы

```powershell
docker compose exec db psql -U iot -d iot -c "\d device"
```

```powershell
docker compose exec db psql -U iot -d iot -c "\d device_capability"
```

```powershell
docker compose exec db psql -U iot -d iot -c "\d measurement_raw"
```

```powershell
docker compose exec db psql -U iot -d iot -c "\d device_state_current"
```

```powershell
docker compose exec db psql -U iot -d iot -c "\d device_availability_event"
```

```powershell
docker compose exec db psql -U iot -d iot -c "\d ingestion_event"
```

---

## Проверить подключение к БД

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT 1;"
```

---

## Посмотреть устройства

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT external_device_id, name, manufacturer, model, protocol, transport, room, last_seen_at FROM device ORDER BY updated_at DESC;"
```

---

## Посмотреть capabilities устройств

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT d.external_device_id, c.capability_id, c.capability_type, c.direction, c.unit, c.value_type, c.source FROM device_capability c JOIN device d ON d.id = c.device_id ORDER BY d.external_device_id, c.capability_id;"
```

---

## Посмотреть последние измерения

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT event_ts, server_received_at, metric, capability_id, value_num, value_text, value_bool, unit, seq FROM measurement_raw ORDER BY server_received_at DESC LIMIT 20;"
```

---

## Посмотреть текущие значения устройства

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT d.external_device_id, s.capability_id, c.capability_type, s.value_num, s.value_text, s.value_bool, s.unit, s.event_ts FROM device_state_current s JOIN device d ON d.id = s.device_id LEFT JOIN device_capability c ON c.device_id = s.device_id AND c.capability_id = s.capability_id ORDER BY d.external_device_id, s.capability_id;"
```

---

## Посмотреть availability events

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT a.event_ts, a.server_received_at, d.external_device_id, a.status, a.reason FROM device_availability_event a JOIN device d ON d.id = a.device_id ORDER BY a.server_received_at DESC LIMIT 20;"
```

---

## Посмотреть ingestion audit log

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT server_received_at, message_type, device_external_id, status, error_code, left(raw_payload_text, 160) AS payload_preview FROM ingestion_event ORDER BY server_received_at DESC LIMIT 20;"
```

---

## Посмотреть только ошибки ingestion

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT server_received_at, mqtt_topic, message_type, device_external_id, status, error_code, error_message FROM ingestion_event WHERE status = 'error' ORDER BY server_received_at DESC LIMIT 20;"
```

---

## Посмотреть warnings

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT server_received_at, mqtt_topic, message_type, device_external_id, status, error_code, error_message FROM ingestion_event WHERE status = 'accepted_with_warnings' ORDER BY server_received_at DESC LIMIT 20;"
```

---

# Диагностика MQTT

## Проверить, что Mosquitto опубликован наружу

```powershell
docker compose ps mosquitto
```

Ожидаемо:

```text
0.0.0.0:1883->1883/tcp
```

---

## Подписаться на все project topics с host-машины

Если `mosquitto_sub` установлен локально:

```powershell
mosquitto_sub -h localhost -p 1883 -t "home/iot/v1/#" -v
```

Через Docker:

```powershell
docker run --rm -it --network iotassistant_default eclipse-mosquitto:2.0 mosquitto_sub -h mosquitto -p 1883 -t "home/iot/v1/#" -v
```

---

## Отправить тестовую telemetry

```powershell
docker run --rm --network iotassistant_default eclipse-mosquitto:2.0 mosquitto_pub -h mosquitto -p 1883 -t "home/iot/v1/device/lab-mqtt-01/telemetry" -q 1 -m "{\"schema_version\":1,\"device_id\":\"lab-mqtt-01\",\"ts\":\"2026-05-25T14:00:00Z\",\"seq\":999,\"measurements\":{\"temperature\":23.4}}"
```

---

## Отправить telemetry с неизвестной metric

```powershell
docker run --rm --network iotassistant_default eclipse-mosquitto:2.0 mosquitto_pub -h mosquitto -p 1883 -t "home/iot/v1/device/lab-mqtt-01/telemetry" -q 1 -m "{\"schema_version\":1,\"device_id\":\"lab-mqtt-01\",\"ts\":\"2026-05-25T14:01:00Z\",\"seq\":1000,\"measurements\":{\"temperature\":23.4,\"unknown_metric\":123}}"
```

Ожидаемо:

```text
temperature записывается в measurement_raw
unknown_metric игнорируется
ingestion_event.status = accepted_with_warnings
```

---

## Отправить telemetry для неизвестного устройства

```powershell
docker run --rm --network iotassistant_default eclipse-mosquitto:2.0 mosquitto_pub -h mosquitto -p 1883 -t "home/iot/v1/device/no-such-device/telemetry" -q 1 -m "{\"schema_version\":1,\"device_id\":\"no-such-device\",\"ts\":\"2026-05-25T14:02:00Z\",\"seq\":1,\"measurements\":{\"temperature\":23.4}}"
```

Ожидаемо:

```text
ingestion_event.status = error
ingestion_event.error_code = unknown_device
```

---

## Очистить retained discovery

```powershell
docker run --rm --network iotassistant_default eclipse-mosquitto:2.0 mosquitto_pub -h mosquitto -p 1883 -t "home/iot/v1/discovery/lab-mqtt-01" -r -n
```

## Очистить retained availability

```powershell
docker run --rm --network iotassistant_default eclipse-mosquitto:2.0 mosquitto_pub -h mosquitto -p 1883 -t "home/iot/v1/device/lab-mqtt-01/availability" -r -n
```

---

# Миграции БД

## Назначение

`deploy/db/schema.sql` — baseline-схема для новой dev-БД.

`deploy/db/migrations/` — изменения поверх уже существующей БД.

`tools/db/migrate.py` применяет только новые migration-файлы и записывает применённые версии в таблицу:

```text
schema_migrations
```

Версия миграции — это имя файла.

Пример:

```text
deploy/db/migrations/
  001_add_device_location.sql
  002_add_capability_check_constraints.sql
```

---

## Проверить применённые миграции

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT version, applied_at FROM schema_migrations ORDER BY applied_at;"
```

---

## Ручной запуск мигратора

```powershell
docker compose up --build migrate
```

Если новых миграций нет, migrator должен завершиться успешно с сообщением:

```text
no migration files found, nothing to apply
```

или:

```text
migration already applied ...
migrations complete
```

---

## Добавление новой миграции

1. Создать новый файл:

```text
deploy/db/migrations/001_some_change.sql
```

2. Записать туда SQL-изменения, например:

```sql
ALTER TABLE device
ADD COLUMN location TEXT;
```

3. Применить:

```powershell
docker compose up --build migrate
```

4. Проверить:

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT version, applied_at FROM schema_migrations ORDER BY applied_at;"
```

---

## Правила миграций

```text
1. Уже применённые migration-файлы не редактировать.
2. Уже применённые migration-файлы не переименовывать.
3. Новое изменение схемы — новый файл.
4. Файлы сортируются по имени, поэтому использовать числовой префикс: 001, 002, 003.
5. Не добавлять в migrations изменения, которые уже есть в baseline schema.sql.
```

---

## Когда менять schema.sql

`schema.sql` — это baseline для новой БД.

На текущем dev-этапе допустимо обновлять `schema.sql`, если меняется итоговая модель. Но если изменение уже применялось к существующей БД через migration-файл, тогда:

```text
schema.sql обновляется как итоговый snapshot,
migration-файл остаётся как история перехода.
```

---

## Пример полного dev-reset с baseline schema

```powershell
docker compose down -v
docker compose up -d --build
```

Если `schema.sql` смонтирован в PostgreSQL init directory:

```text
/docker-entrypoint-initdb.d/001_schema.sql
```

то при создании пустого volume PostgreSQL применит его автоматически.

После этого можно применить будущие миграции:

```powershell
docker compose up --build migrate
```

---

# Быстрая проверка после старта

После:

```powershell
docker compose up -d --build
```

Проверить сервисы:

```powershell
docker compose ps
```

Проверить worker:

```powershell
docker compose logs --tail=100 worker
```

Проверить БД:

```powershell
docker compose exec db psql -U iot -d iot -c "\dt"
```

Проверить ingestion:

```powershell
docker compose exec db psql -U iot -d iot -c "SELECT server_received_at, message_type, device_external_id, status, error_code FROM ingestion_event ORDER BY server_received_at DESC LIMIT 10;"
```