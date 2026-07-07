# Сервис назначения ревьюеров на PR

HTTP-сервис для назначения ревьюеров на PR по тестовому заданию.

## Стек

- Python 3.14
- FastAPI
- PostgreSQL 18
- асинхронный SQLAlchemy + asyncpg
- Alembic
- uv
- pytest
- ruff
- mypy
- Prometheus
- Grafana
- PostgreSQL exporter
- Loki + Promtail
- k6

## Запуск

Сервис и PostgreSQL поднимаются одной командой:

```bash
docker compose up --build
```

При старте контейнера приложения автоматически выполняется:

```bash
alembic upgrade head
```

После запуска API доступно на `http://localhost:8080`.

Документация API доступна на:

- `http://localhost:8080/docs`
- `http://localhost:8080/openapi.json`

Сервисы для метрик и логов:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Loki: `http://localhost:3100`
- PostgreSQL exporter: `http://localhost:9187`

Логин Grafana по умолчанию: `admin`, пароль: `admin`.

## Конфигурация

Настройки читаются из переменных окружения через `pydantic-settings`.

Основные переменные:

```bash
APP_HOST=0.0.0.0
APP_PORT=8080
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/pr_reviewer_assignment
DATABASE_ECHO=false
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
```

Для локального Docker Compose эти значения уже заданы в `docker-compose.yml`.

## Проверки

Установить зависимости:

```bash
uv sync --dev
```

Запустить все тесты:

```bash
uv run pytest
```

Запустить отдельные группы:

```bash
uv run pytest -m unit
uv run pytest -m e2e
uv run pytest -m integration
```

Интеграционные тесты используют Testcontainers и требуют доступный Docker.

Линтер, форматирование и типизация:

```bash
uv run ruff check src migrations tests
uv run ruff format --check src migrations tests
uv run mypy src migrations tests
```

## Тесты

В проекте есть три слоя тестов:

- `unit`: бизнес-правила, привязка доменных ошибок к HTTP, схемы и валидация.
- `e2e`: HTTP-сценарии через FastAPI ASGI без внешней БД.
- `integration`: реальные PostgreSQL 18, миграции Alembic, репозитории и транзакционный слой через Testcontainers.

Покрыты ключевые сценарии:

- создание команды;
- получение команды;
- изменение активности пользователя;
- массовая деактивация команды с безопасным переназначением открытых PR;
- создание PR с назначением 0/1/2 ревьюеров;
- идемпотентный merge;
- переназначение ревьюера;
- контрактные ошибки `TEAM_EXISTS`, `PR_EXISTS`, `PR_MERGED`, `NOT_ASSIGNED`, `NO_CANDIDATE`, `NOT_FOUND`;
- валидация входных строк до обращения к БД.

## Линтер и форматирование

Конфигурация лежит в `pyproject.toml`.

Используется `ruff`:

- длина строки: `88`;
- целевая версия Python: `py314`;
- форматирование в стиле Black с двойными кавычками;
- включены правила `E`, `F`, `UP`, `B`, `SIM`, `I`.

`mypy` настроен с `mypy_path = "src"`, чтобы одинаково проверять `src`, `migrations` и `tests`.

## Наблюдаемость

Сервис отдает Prometheus-метрики на `GET /metrics`.

Основные метрики приложения:

- `app_http_requests_total` — количество HTTP-запросов по method/path/status.
- `app_http_request_duration_seconds` — время обработки HTTP-запросов.
- `app_http_requests_in_progress` — текущие запросы в обработке.
- `app_db_queries_total` — количество SQL-запросов по типу операции.
- `app_db_query_duration_seconds` — длительность SQL-запросов.

Prometheus забирает метрики с `app:8080/metrics` по конфигу `observability/prometheus/prometheus.yml`.
PostgreSQL exporter отдаёт метрики БД на `postgres-exporter:9187`.

Grafana автоматически получает источники данных для Prometheus и Loki из `observability/grafana/provisioning`.
Панель `PR Reviewer Assignment / Load Testing` подхватывается из `observability/grafana/dashboards`.

Логи контейнера приложения дополнительно пишутся в том Docker `app_logs`.
Promtail читает этот том и отправляет записи в Loki. Конфигурация лежит в `observability/promtail/config.yml`.

Если Grafana уже была запущена до добавления панели, перезапусти её:

```bash
docker compose restart grafana
```

На чистом томе Docker панель появится автоматически в папке `PR Reviewer Assignment`.

## Нагрузочное тестирование

Для нагрузки используется `k6`. Чтобы результаты с локальной машины и VPS можно
было сравнивать между собой, есть отдельный compose-файл:

```bash
docker-compose.load.yml
```

В нём приложение и PostgreSQL ограничены одинаково: по `1 CPU` и `1 GiB RAM`.

Поднять стенд с лимитами:

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml up --build -d app postgres prometheus grafana loki promtail postgres-exporter
```

Быстрая проверка, что всё поднялось и отвечает:

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml --profile load run --rm -e WORKLOAD=smoke k6
```

Проверка SLI из задания:

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml --profile load run --rm -e WORKLOAD=sli -e TARGET_RATE=5 -e DURATION=5m k6
```

В этом режиме перед тестом создаются 20 команд и 200 пользователей, а одна итерация
равна одному HTTP-запросу. Поэтому `TARGET_RATE=5` действительно означает примерно
5 HTTP RPS, как в `TASK.md`.

Смешанный сценарий для проверки запаса:

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml --profile load run --rm -e WORKLOAD=api_mix -e TARGET_RATE=1 -e DURATION=5m k6
```

В `api_mix` параметр `TARGET_RATE` задаёт не HTTP RPS, а количество полных сценариев
в секунду. Один такой сценарий делает несколько запросов подряд: создаёт команду,
создаёт PR, читает данные, делает переназначение и merge. Поэтому `TARGET_RATE=20`
в последнем прогоне дал около 142 HTTP RPS.

Отдельная проверка массовой деактивации команды:

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml --profile load run --rm -e WORKLOAD=deactivate -e TARGET_RATE=10 -e DURATION=5m k6
```

Более подробная инструкция лежит в `load-tests/README.md`.

### Методика нагрузочного тестирования

Я разделял проверку на две части. Сначала запускался сценарий из задания, где нужно
держать p95 ниже 300 мс при 5 RPS. Потом запускался более тяжёлый смешанный сценарий,
чтобы понять, где начнут появляться узкие места.

Тестовый стенд для локальных прогонов:

- CPU: Intel Core i5-12450H;
- RAM: 16 GiB;
- Docker Desktop;
- `app`: ограничен `1 CPU` и `1 GiB RAM`;
- `postgres`: ограничен `1 CPU` и `1 GiB RAM`;
- настройки PostgreSQL: `shared_buffers=256MB`, `effective_cache_size=768MB`, `work_mem=8MB`, `maintenance_work_mem=64MB`, `max_connections=50`;
- пул соединений приложения: `DATABASE_POOL_SIZE=5`, `DATABASE_MAX_OVERFLOW=10`;
- в нагрузочном профиле uvicorn запускается с `--no-access-log`, чтобы логирование каждого запроса не портило хвост задержек.

Перед новым прогоном база очищалась полностью:

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml down -v
```

Если нужно было сохранить метрики и панели, очищались только бизнес-таблицы:

```bash
docker compose exec postgres psql -U postgres -d pr_reviewer_assignment -c "TRUNCATE pull_request_reviewers, pull_requests, users, teams RESTART IDENTITY CASCADE;"
```

За состоянием сервиса я смотрел в нескольких местах: сводка k6, Grafana, метрики
приложения, метрики PostgreSQL exporter и `docker stats` для контейнеров app/postgres.
Особенно полезными оказались p95/p99 по HTTP, p95 по SQL, количество SQL-запросов,
загрузка CPU и число активных соединений с БД.

### Настройки k6

Скрипт нагрузки лежит в `load-tests/k6/pr_reviewer_assignment.js`. Основные параметры
передаются через переменные окружения:

- `WORKLOAD`: `smoke`, `sli`, `api_mix`, `deactivate`;
- `START_RATE`: начальная скорость подачи запросов;
- `TARGET_RATE`: целевая скорость;
- `DURATION`: длительность основной части теста;
- `RAMP_UP` и `RAMP_DOWN`: разгон и сброс нагрузки;
- `PRE_ALLOCATED_VUS` и `MAX_VUS`: запас виртуальных пользователей;
- `SLO_P95_MS`: порог p95, по умолчанию `300`;
- `SLI_TEAMS`, `SLI_USERS_PER_TEAM`, `SLI_SEED_PRS`: размер набора данных для `WORKLOAD=sli`.

У запросов есть теги `endpoint`, `name` и `phase`. `name` нужен, чтобы k6 не создавал
отдельную временную серию для каждого URL с уникальными query-параметрами. `phase`
разделяет подготовку данных и саму нагрузку; пороги SLO считаются только по `phase:load`.

Для `POST /pullRequest/reassign` статус `409` считается ожидаемым бизнес-исходом.
Например, если PR уже смёржен или подходящего кандидата нет, API корректно возвращает
доменную ошибку. В k6 это явно помечено через `http.expectedStatuses(..., 409)`,
иначе `http_req_failed` считал бы любой `409` технической ошибкой.

### Результаты и оптимизации

Контрактный прогон `WORKLOAD=sli TARGET_RATE=5` после оптимизаций прошёл с большим
запасом:

- общий `http_req_duration p95`: `22.59ms`;
- `create_pr p95`: `17.63ms`;
- средняя задержка: `10.21ms`;
- фактическая нагрузка: около `4.8 HTTP RPS`.

В одном из прогонов `http_req_failed` был красным: `6.50%`, хотя все проверки сценария
были зелёными. Причина оказалась не в падениях сервиса. К концу теста часть заранее
созданных PR уже была переведена в `MERGED`, и `reassign` ожидаемо отвечал
`409 PR_MERGED`. Для бизнес-логики это нормальный ответ, но k6 по умолчанию считает
любой `4xx` ошибкой. После явной настройки ожидаемых статусов эта проблема ушла.

Стресс-тест `WORKLOAD=api_mix TARGET_RATE=20` после оптимизаций:

- общий `http_req_duration p95`: `278.79ms`;
- `create_pr p95`: `302.69ms`;
- `http_req_failed`: `0%`;
- фактическая нагрузка: около `142 HTTP RPS`;
- `dropped_iterations`: `7` за 6m30s.

Этот сценарий существенно тяжелее SLI из задания: каждая итерация делает несколько
последовательных HTTP-запросов и пишет новые команды/PR в БД. Поэтому промах
`create_pr` на несколько миллисекунд в стресс-тесте не означает провал контрактного SLI.

Что было найдено и исправлено:

- Первые прогоны показывали высокий HTTP p95 при нормальном SQL p95 около `50ms`.
  Узкое место было не в одном медленном SQL-запросе, а в количестве походов из API в БД.
- В `create_pull_request` успешный путь сокращён примерно с пяти обращений к БД до трёх:
  создание PR выполняется через `INSERT ... SELECT ... ON CONFLICT DO NOTHING RETURNING`,
  а автор вместе с активными участниками команды читается одним запросом.
- В `merge_pull_request` обновление статуса и возврат актуального PR объединены через
  `UPDATE ... RETURNING` с агрегацией ревьюеров, вместо отдельного обновления и повторного чтения.
- Для чтений, чувствительных к N+1, используются агрегирующие запросы и упорядочивание на стороне БД:
  `get_by_name`, `get_by_id`, `list_by_reviewer`.
- Для частых фильтров добавлены индексы:
  `users(team_name, is_active, user_id)`,
  `pull_requests(author_id)`,
  `pull_request_reviewers(reviewer_id, pull_request_id)`.
- В нагрузочном профиле выключен журнал доступа uvicorn, потому что поток логов при высокой частоте запросов заметно ухудшал p95/p99.
- Для k6 добавлена группировка URL через тег `name`, чтобы запросы с уникальными query-параметрами не создавали десятки тысяч временных серий.
- Входные ограничения строк вынесены в `src/core/domain/constraints.py` и используются и в SQLAlchemy, и в Pydantic.
  Поэтому слишком длинные значения теперь дают `422`, а не позднюю `500` от БД.

Оставшиеся ограничения методики:

- Локальный запуск на Docker Desktop не равен выделенному Linux-серверу: есть накладные расходы виртуализации, файловой системы и сети.
- `api_mix` постоянно создаёт новые данные, поэтому поздние минуты теста работают на большем объёме таблиц, чем первые.
- `reassign` и `merge` в `sli` конкурируют за заранее созданные PR: это полезно для проверки доменных конфликтов, но не является чистым тестом чтения или записи.
- Prometheus/Grafana/Loki работают на той же машине и тоже потребляют ресурсы, хотя app/postgres ограничены отдельными лимитами.
- Для финального сравнения локальной машины и VPS нужно запускать один и тот же нагрузочный compose-профиль, с чистой БД и одинаковыми переменными k6.

## Схема БД

Актуальная схема создаётся миграцией `0001_initial_schema`.

```sql
CREATE TYPE pr_status AS ENUM ('OPEN', 'MERGED');

CREATE TABLE teams (
    team_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_teams PRIMARY KEY (team_name)
);

CREATE TABLE users (
    user_id VARCHAR(20) NOT NULL,
    username VARCHAR(100) NOT NULL,
    team_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (user_id),
    CONSTRAINT fk_users_team_name_teams
        FOREIGN KEY (team_name)
        REFERENCES teams (team_name)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE INDEX idx_users_team_active_user_id
    ON users (team_name, is_active, user_id);

CREATE TABLE pull_requests (
    pull_request_id VARCHAR(20) NOT NULL,
    pull_request_name VARCHAR(100) NOT NULL,
    author_id VARCHAR(20) NOT NULL,
    status pr_status DEFAULT 'OPEN' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    merged_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT pk_pull_requests PRIMARY KEY (pull_request_id),
    CONSTRAINT ck_pull_requests_status_merged_at CHECK (
        (status = 'OPEN' AND merged_at IS NULL)
        OR
        (status = 'MERGED' AND merged_at IS NOT NULL)
    ),
    CONSTRAINT fk_pull_requests_author_id_users
        FOREIGN KEY (author_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE INDEX idx_pull_requests_author_id
    ON pull_requests (author_id);

CREATE TABLE pull_request_reviewers (
    pull_request_id VARCHAR(20) NOT NULL,
    reviewer_id VARCHAR(20) NOT NULL,
    slot SMALLINT NOT NULL,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_pull_request_reviewers
        PRIMARY KEY (pull_request_id, reviewer_id),
    CONSTRAINT ck_pull_request_reviewers_slot_in_range
        CHECK (slot IN (1, 2)),
    CONSTRAINT fk_pull_request_reviewers_pull_request_id_pull_requests
        FOREIGN KEY (pull_request_id)
        REFERENCES pull_requests (pull_request_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_pull_request_reviewers_reviewer_id_users
        FOREIGN KEY (reviewer_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT uq_pull_request_reviewers_pull_request_id_slot
        UNIQUE (pull_request_id, slot)
);

CREATE INDEX idx_pull_request_reviewers_reviewer_id_pull_request_id
    ON pull_request_reviewers (reviewer_id, pull_request_id);
```

Строковые ограничения вынесены в `src/core/domain/constraints.py` и используются и в SQLAlchemy-моделях, и во входных Pydantic-схемах.

## Основные API-сценарии

1. `POST /team/add`

   Создаёт команду с участниками. Участники создаются или обновляются.
   Если `user_id` уже был в другой команде, пользователь переносится в новую.

   Ошибка: команда уже существует -> `400 TEAM_EXISTS`.

2. `GET /team/get?team_name=...`

   Возвращает команду и всех участников.

   Ошибка: команда не найдена -> `404 NOT_FOUND`.

3. `POST /users/setIsActive`

   Меняет активность пользователя.

   Уже существующие назначения в открытых PR не меняются. Активность влияет на будущие назначения и переназначения.

   Ошибка: пользователь не найден -> `404 NOT_FOUND`.

4. `POST /team/deactivate`

   Деактивирует всех участников команды и заранее переназначает их открытые PR на активных пользователей из `replacement_team_name`.

   Операция атомарная: если хотя бы для одного открытого PR нельзя подобрать замену, пользователи не деактивируются и назначения не меняются.

   Запрос:

   ```json
   {
     "team_name": "backend",
     "replacement_team_name": "platform"
   }
   ```

   В `reassignments` возвращается список выполненных замен.

   Ошибки:

   - команда или команда для замены не найдена -> `404 NOT_FOUND`;
   - нет подходящего кандидата для всех открытых PR -> `409 NO_CANDIDATE`.

5. `POST /pullRequest/create`

   Создаёт PR в статусе `OPEN` и назначает до двух активных ревьюеров из команды автора, исключая автора.

   Если доступных кандидатов 0 или 1, назначается 0 или 1 ревьюер. Это не ошибка.

   Ошибки:

   - автор не найден -> `404 NOT_FOUND`;
   - PR уже существует -> `409 PR_EXISTS`.

6. `POST /pullRequest/merge`

   Переводит PR в `MERGED` и выставляет `mergedAt`.

   Операция идемпотентная: повторный merge возвращает актуальный PR без ошибки.

   Ошибка: PR не найден -> `404 NOT_FOUND`.

7. `POST /pullRequest/reassign`

   Заменяет `old_user_id` на нового активного ревьюера из команды старого ревьюера.

   Новый ревьюер не может быть автором PR, старым ревьюером или уже назначенным ревьюером.

   Ошибки:

   - PR или пользователь не найден -> `404 NOT_FOUND`;
   - PR уже `MERGED` -> `409 PR_MERGED`;
   - `old_user_id` не назначен на PR -> `409 NOT_ASSIGNED`;
   - нет подходящего кандидата -> `409 NO_CANDIDATE`.

8. `GET /users/getReview?user_id=...`

   Возвращает список PR, где пользователь назначен ревьюером.

   По контракту для этой ручки не описан `404`, поэтому для несуществующего пользователя возвращается пустой список.

9. `GET /health`

   Проверяет состояние сервиса и доступность БД.

   Успешный ответ: `{ "status": "ok", "database": "ok" }`.

   Если БД недоступна, возвращает `503` и статус `degraded`.

10. `GET /stats`

   Возвращает агрегированную статистику сервиса:

   - количество команд;
   - количество пользователей;
   - количество активных и неактивных пользователей;
   - количество PR по статусам;
   - количество назначений;
   - назначения по пользователям;
   - количество ревьюеров по PR.

11. `GET /metrics`

   Возвращает метрики в формате Prometheus.

## Принятые допущения

- Пользователь принадлежит только одной команде. Если тот же `user_id` передан при создании другой команды, пользователь переносится в новую команду.
- `is_active = false` не снимает уже существующие назначения в открытых PR.
- Для безопасной массовой деактивации команды нужно использовать `POST /team/deactivate`.
- `POST /team/deactivate` меняет только открытые PR; назначения в `MERGED` PR остаются историей и не переписываются.
- После `MERGED` список ревьюеров менять нельзя.
- `getReview` для несуществующего пользователя возвращает пустой список, потому что в контракте нет ошибки для этого случая.
- Входные строки валидируются на уровне API: пустые после удаления пробелов значения и значения длиннее БД-лимитов возвращают `422`.
