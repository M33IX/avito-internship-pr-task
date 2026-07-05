from api.v1.pull_requests.schemas import (
    CreatePrRequest,
    CreatePrResponse,
    MergePrRequest,
    MergePrResponse,
    ReassignPrRequest,
    ReassignPrResponse,
)


class PRService:
    async def create_pr(self, request: CreatePrRequest) -> CreatePrResponse: ...

    async def merge_pr(self, request: MergePrRequest) -> MergePrResponse: ...

    async def reassign_reviewer(
        self,
        request: ReassignPrRequest,
    ) -> ReassignPrResponse: ...
