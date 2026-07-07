from api.v1.pull_requests.schemas import PullRequestShort as PullRequestShortSchema
from api.v1.users.schemas import (
    GetReviewResponse,
    SetIsActiveRequest,
    SetIsActiveResponse,
)
from api.v1.users.schemas import (
    User as UserSchema,
)
from core.application.use_cases import (
    SetUserActivityCommand,
    get_user_review_pull_requests,
    set_user_activity,
)
from core.domain.entities import PullRequestShort, User
from core.interfaces.logger import ILogger
from core.interfaces.uow import IUnitOfWork


class UsersService:
    def __init__(
        self,
        uow: IUnitOfWork,
        logger: ILogger,
    ) -> None:
        self._uow = uow
        self._logger = logger

    async def get_user_prs(self, user_id: str) -> GetReviewResponse:
        pull_requests = await get_user_review_pull_requests(
            user_id=user_id,
            uow=self._uow,
            logger=self._logger,
        )
        return GetReviewResponse(
            user_id=user_id,
            pull_requests=[
                pull_request_short_to_schema(pull_request)
                for pull_request in pull_requests
            ],
        )

    async def set_user_activity_status(
        self,
        request: SetIsActiveRequest,
    ) -> SetIsActiveResponse:
        user = await set_user_activity(
            command=SetUserActivityCommand(
                user_id=request.user_id,
                is_active=request.is_active,
            ),
            uow=self._uow,
            logger=self._logger,
        )
        return SetIsActiveResponse(user=user_to_schema(user))


def user_to_schema(user: User) -> UserSchema:
    return UserSchema(
        user_id=user.user_id,
        username=user.username,
        team_name=user.team_name,
        is_active=user.is_active,
    )


def pull_request_short_to_schema(
    pull_request: PullRequestShort,
) -> PullRequestShortSchema:
    return PullRequestShortSchema(
        pull_request_id=pull_request.pull_request_id,
        pull_request_name=pull_request.pull_request_name,
        author_id=pull_request.author_id,
        status=pull_request.status,
    )
