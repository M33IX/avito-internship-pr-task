# PR Reviewer Assignment Service

## Стек

- Python 3.14.2
- FastAPI
- Postgres 18
- uv
- ruff

## Принятые допущения

- В ТЗ не указано, что юзер может принадлежать нескольким командам, поэтому каждый юзер может быть только в одной команде и, при создании новой группы, юзеры из старой группы переносятся в новую (если они указаны при создании группы)

- При изменении статуса юзера в `isActive = False`: если пользователь уже был назначен ревьюером в открытых PR, эти назначения не трогаем. Активность влияет только на будущие назначения и переназначения.

- При создании PR, если кандидатов на ревьюеров 0 или 1, то назначаем 0 или 1 соответствунно

- При получении списков PR на ревью пользователя: Если у юзера нет PR, то возвращается пустой список. Если юзера нет, то вернется тоже пустой список, поскольку в getReview openapi схеме нет 404 ошибки

## Схема БД

CREATE TYPE pr_status AS ENUM ('OPEN', 'MERGED');

CREATE TABLE teams (
    team_name VARCHAR(20) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    user_id VARCHAR(20) PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    team_name VARCHAR(100) NOT NULL REFERENCES teams(team_name)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_team_active_user_id
    ON users(team_name, is_active, user_id);

CREATE TABLE pull_requests (
    pull_request_id VARCHAR(20) PRIMARY KEY,
    pull_request_name VARCHAR(100) NOT NULL,
    author_id VARCHAR(20) NOT NULL REFERENCES users(user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    status pr_status NOT NULL DEFAULT 'OPEN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    merged_at TIMESTAMPTZ,

    CHECK (
        (status = 'OPEN' AND merged_at IS NULL)
        OR
        (status = 'MERGED' AND merged_at IS NOT NULL)
    )
);

CREATE INDEX idx_pull_requests_author_id
    ON pull_requests(author_id);

CREATE TABLE pull_request_reviewers (
    pull_request_id VARCHAR(20) NOT NULL REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id VARCHAR(20) NOT NULL REFERENCES users(user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    slot SMALLINT NOT NULL CHECK (slot IN (1, 2)),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (pull_request_id, reviewer_id),
    UNIQUE (pull_request_id, slot)
);

CREATE INDEX idx_pull_request_reviewers_reviewer_id_pull_request_id
    ON pull_request_reviewers(reviewer_id, pull_request_id);


## Основные юзкейсы

1. Создать команду
   `POST /team/add`

   Создаёт новую команду с уникальным `team_name`. Участники из `members` создаются или обновляются. Если `user_id` уже был в другой команде, переносим пользователя в новую команду и обновляем `username/is_active`.

   Ошибка: команда уже существует → `400 TEAM_EXISTS`.

2. Получить команду
   `GET /team/get?team_name=...`

   Возвращает команду и всех её участников.

   Ошибка: команды нет → `404 NOT_FOUND`.

3. Изменить активность пользователя
   `POST /users/setIsActive`

   Меняет `is_active` у пользователя и возвращает обновлённого пользователя.

   Важно: если пользователь уже был назначен ревьюером в открытых PR, эти назначения не трогаем. Активность влияет только на будущие назначения и переназначения.

   Ошибка: пользователя нет → `404 NOT_FOUND`.

4. Создать PR
   `POST /pullRequest/create`

   Создаёт PR в статусе `OPEN` и автоматически назначает до двух ревьюеров:
   активные пользователи из команды автора, кроме самого автора.

   Если кандидатов 0 или 1, назначаем 0 или 1 соответственно. Это не ошибка.

   Ошибки:
   - автора нет или у автора нет команды → `404 NOT_FOUND`
   - PR с таким id уже существует → `409 PR_EXISTS`

5. Смержить PR
   `POST /pullRequest/merge`

   Переводит PR в `MERGED`, выставляет `mergedAt`, возвращает актуальный PR.

   Операция идемпотентная: повторный merge уже смерженного PR не ошибка, просто возвращаем тот же PR в состоянии `MERGED`.

   Ошибка: PR нет → `404 NOT_FOUND`.

6. Переназначить ревьюера
   `POST /pullRequest/reassign`

   Заменяет конкретного ревьюера `old_user_id` на нового кандидата.

   Допустимый новый ревьюер:
   активный участник команды старого ревьюера, не автор PR, не старый ревьюер и не уже назначенный ревьюер.

   Ошибки:
   - PR или пользователь не найден → `404 NOT_FOUND`
   - PR уже `MERGED` → `409 PR_MERGED`
   - `old_user_id` не назначен ревьюером на этот PR → `409 NOT_ASSIGNED`
   - нет подходящего кандидата → `409 NO_CANDIDATE`

7. Получить PR на ревью пользователя
   `GET /users/getReview?user_id=...`

   Возвращает список PR, где пользователь находится в `assigned_reviewers`. По контракту ошибки нет, но логически можно возвращать пустой список, если PR нет. Для несуществующего пользователя контракт тоже не описывает `404`, так что лучше держаться контракта и вернуть `{ user_id, pull_requests: [] }`, если не договоримся иначе.
