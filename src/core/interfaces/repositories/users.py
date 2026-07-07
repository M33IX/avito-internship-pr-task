from typing import Protocol

from core.domain.entities import TeamMember, User
from core.interfaces.repositories.base import IRepository


class IUsersRepository(IRepository, Protocol):
    async def get_by_id(self, user_id: str) -> User | None: ...

    async def get_with_active_teammates(
        self,
        user_id: str,
    ) -> tuple[User, list[User]] | None: ...

    async def upsert_many(
        self,
        team_name: str,
        users: list[TeamMember],
    ) -> None: ...

    async def set_active(
        self,
        user_id: str,
        is_active: bool,
    ) -> User | None: ...

    async def deactivate_by_team(self, team_name: str) -> None: ...

    async def list_active_by_team(
        self,
        team_name: str,
        exclude_user_ids: set[str] | None = None,
        limit: int | None = None,
    ) -> list[User]: ...

    async def count(self) -> int: ...

    async def count_by_activity(self, *, is_active: bool) -> int: ...
