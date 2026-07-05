from api.v1.users.schemas import (
    GetReviewResponse,
    SetIsActiveRequest,
    SetIsActiveResponse,
)


class UsersService:
    async def get_user_prs(self, user_id: str) -> GetReviewResponse: ...

    async def set_user_activity_status(
        self,
        request: SetIsActiveRequest,
    ) -> SetIsActiveResponse: ...
