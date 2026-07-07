from core.domain.entities import ServiceStats
from core.domain.enums.pull_requests import PRStatus
from core.interfaces.logger import ILogger
from core.interfaces.uow import IUnitOfWork


async def get_service_stats(
    uow: IUnitOfWork,
    logger: ILogger,
) -> ServiceStats:
    stats = ServiceStats(
        teams=await uow.teams.count(),
        users=await uow.users.count(),
        active_users=await uow.users.count_by_activity(is_active=True),
        inactive_users=await uow.users.count_by_activity(is_active=False),
        pull_requests=await uow.pull_requests.count(),
        open_pull_requests=await uow.pull_requests.count_by_status(PRStatus.OPEN),
        merged_pull_requests=await uow.pull_requests.count_by_status(PRStatus.MERGED),
        assignments=await uow.pull_request_reviewers.count(),
        assignments_by_user=await uow.pull_request_reviewers.count_by_user(),
        reviewers_by_pull_request=(
            await uow.pull_request_reviewers.count_by_pull_request()
        ),
    )
    logger.info(
        "service stats fetched",
        teams=stats.teams,
        users=stats.users,
        pull_requests=stats.pull_requests,
        assignments=stats.assignments,
    )
    return stats
