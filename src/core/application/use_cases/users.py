from dataclasses import dataclass

from core.domain.entities import PullRequestShort, User
from core.exceptions import UserNotFoundError
from core.interfaces.logger import ILogger
from core.interfaces.uow import IUnitOfWork


@dataclass(slots=True, kw_only=True)
class SetUserActivityCommand:
    user_id: str
    is_active: bool


async def get_user_review_pull_requests(
    user_id: str,
    uow: IUnitOfWork,
    logger: ILogger,
) -> list[PullRequestShort]:
    pull_requests = await uow.pull_requests.list_by_reviewer(user_id)
    logger.info(
        "user review pull requests fetched",
        user_id=user_id,
        pull_requests_count=len(pull_requests),
    )
    return pull_requests


async def set_user_activity(
    command: SetUserActivityCommand,
    uow: IUnitOfWork,
    logger: ILogger,
) -> User:
    user = await uow.users.set_active(
        user_id=command.user_id,
        is_active=command.is_active,
    )
    if user is None:
        logger.warning("user not found", user_id=command.user_id)
        raise UserNotFoundError("resource not found")

    await uow.commit()
    logger.info(
        "user activity status changed",
        user_id=user.user_id,
        is_active=user.is_active,
    )
    return user
