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

CREATE INDEX idx_users_team_active
    ON users(team_name, is_active);

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

CREATE INDEX idx_pull_request_reviewers_reviewer_id
    ON pull_request_reviewers(reviewer_id);