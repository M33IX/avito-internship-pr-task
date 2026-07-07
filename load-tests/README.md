# Нагрузочное тестирование

Для нагрузочного тестирования используется `k6` в Docker. Один и тот же запуск работает локально и на VPS.

## Стек

- `k6` — генератор нагрузки.
- Prometheus — метрики приложения, SQLAlchemy и PostgreSQL.
- Grafana — визуализация.
- PostgreSQL exporter — метрики БД.
- Loki + Promtail — логи приложения.

## Ресурсные лимиты

Для корректного сравнения локальной машины и VPS используется дополнительный compose-файл:

```bash
docker-compose.load.yml
```

В нём:

- `app`: `1 CPU`, `1 GiB RAM`;
- `postgres`: `1 CPU`, `1 GiB RAM`;
- PostgreSQL дополнительно настроен под 1 GiB RAM.

Проверить фактические лимиты и потребление:

```bash
docker stats avito-internship-app avito-internship-postgres
```

## Запуск стенда

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml up --build -d app postgres prometheus grafana loki promtail postgres-exporter
```

API:

```bash
http://localhost:8080
```

Grafana:

```bash
http://localhost:3000
```

Панель Grafana:

```bash
PR Reviewer Assignment / Load Testing
```

Она автоматически подхватывается из `observability/grafana/dashboards` и находится в папке `PR Reviewer Assignment`.

Prometheus:

```bash
http://localhost:9090
```

## Быстрая проверка

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml --profile load run --rm -e WORKLOAD=smoke k6
```

## Основной смешанный сценарий

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml --profile load run --rm \
  -e WORKLOAD=api_mix \
  -e TARGET_RATE=1 \
  -e DURATION=5m \
  k6
```

`api_mix` создаёт команды и PR, читает команды и назначения ревьюеров, делает переназначение и merge.
В этом сценарии `TARGET_RATE` задаёт количество полных сценариев в секунду, а не HTTP RPS. Один сценарий делает несколько HTTP-запросов, поэтому `TARGET_RATE=1` обычно даёт около 7 HTTP RPS. Для проверки SLI из задания лучше начинать с `TARGET_RATE=1`, а потом поднимать нагрузку ступенями.

## Проверка SLI по условиям задания

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml --profile load run --rm \
  -e WORKLOAD=sli \
  -e TARGET_RATE=5 \
  -e DURATION=5m \
  k6
```

`sli` перед прогоном создаёт ограниченный набор данных из 20 команд и 200 пользователей, затем делает один HTTP-запрос на итерацию. Поэтому `TARGET_RATE=5` соответствует примерно 5 HTTP RPS из `TASK.md`.

Подготовка данных помечается тегом `phase:setup`, а основная нагрузка — `phase:load`.
Пороги считаются по `phase:load`, чтобы создание тестовых данных не влияло на SLO.

## Массовая деактивация

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml --profile load run --rm \
  -e WORKLOAD=deactivate \
  -e TARGET_RATE=10 \
  -e DURATION=5m \
  k6
```

`deactivate` создаёт основную команду, команду для замены, PR и вызывает `POST /team/deactivate`.

## Рекомендуемый прогон

1. Быстрая проверка: `WORKLOAD=smoke`.
2. Проверка SLI: `WORKLOAD=sli`, `TARGET_RATE=5`, `DURATION=5m`.
3. Базовый смешанный сценарий: `WORKLOAD=api_mix`, `TARGET_RATE=1`, `DURATION=5m`.
4. Ступенчатая нагрузка для `api_mix`: `TARGET_RATE=5`, `10`, `20`, `50`.
5. Отдельно `WORKLOAD=deactivate`.
6. После каждого шага фиксировать:
   - k6 `http_req_duration` p95/p99;
   - k6 `http_req_failed`;
   - `app_http_request_duration_seconds`;
   - `app_db_query_duration_seconds`;
   - `app_db_queries_total`;
   - метрики PostgreSQL exporter;
   - `docker stats` для app/postgres.

По умолчанию k6 проверяет задержку из задания: общий `http_req_duration` p95 должен быть меньше `300ms`. Порог можно временно переопределить:

```bash
-e SLO_P95_MS=500
```

`POST /pullRequest/reassign` может корректно возвращать `409`: например, если PR уже `MERGED` или нет кандидата для замены.
Такие ответы считаются ожидаемыми через `http.expectedStatuses(..., 409)`.
Без этого k6 помечал бы доменный `409` как `http_req_failed`, даже если проверка сценария зелёная.

## Как читать результат

- Если `app_http_request_duration_seconds` растёт, а `app_db_query_duration_seconds` остаётся низкой, узкое место скорее в Python/API слое.
- Если p95/p99 HTTP растёт вместе с `app_db_query_duration_seconds`, смотрим SQL-запросы и индексы.
- Если PostgreSQL CPU близко к 100%, а app CPU ниже, упираемся в БД.
- Если CPU приложения близко к 100%, а CPU БД и SQL-задержки нормальные, упираемся в приложение.
- Если растут ошибки `409`, сначала стоит проверить, не упёрся ли сценарий в доменные конфликты, а не в производительность.
- Если проверки зелёные, но `http_req_failed` красный, проверь ожидаемые статусы: k6 по умолчанию считает `4xx` ошибкой HTTP-слоя.

## Сброс данных между прогонами

Для полностью чистого стенда:

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml down -v
```

Затем заново поднять стенд.

## Результаты

Сводка k6 пишется в:

```bash
load-tests/results/summary.json
```
