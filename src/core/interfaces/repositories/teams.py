from typing import Protocol

from core.domain.entities import Team
from core.interfaces.repositories.base import IRepository


class ITeamsRepository(IRepository, Protocol):
    async def exists(self, team_name: str) -> bool: ...

    async def get_by_name(self, team_name: str) -> Team | None: ...

    async def create(self, team_name: str) -> None: ...

    async def count(self) -> int: ...
