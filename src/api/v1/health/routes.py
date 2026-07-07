from fastapi import APIRouter, status
from fastapi.responses import JSONResponse, Response

from api.v1.dependencies import HealthServiceDep
from api.v1.health.schemas import (
    AssignmentCountResponse,
    HealthResponse,
    HealthStatus,
    PullRequestReviewersCountResponse,
    StatsResponse,
)
from infrastructure.metrics import metrics_response

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Проверить состояние сервиса и подключения к БД",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "Сервис работает, но БД недоступна",
        },
    },
)
async def health(service: HealthServiceDep) -> HealthResponse | JSONResponse:
    try:
        await service.check_database()
    except Exception:
        degraded = HealthResponse(
            status=HealthStatus.DEGRADED,
            database=HealthStatus.DEGRADED,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=degraded.model_dump(mode="json"),
        )

    return HealthResponse(status=HealthStatus.OK, database=HealthStatus.OK)


@router.get(
    "/stats",
    summary="Получить агрегированную статистику сервиса",
    response_model=StatsResponse,
    response_description="Агрегированная статистика",
    status_code=status.HTTP_200_OK,
)
async def stats(service: HealthServiceDep) -> StatsResponse:
    service_stats = await service.get_stats()
    return StatsResponse(
        teams=service_stats.teams,
        users=service_stats.users,
        active_users=service_stats.active_users,
        inactive_users=service_stats.inactive_users,
        pull_requests=service_stats.pull_requests,
        open_pull_requests=service_stats.open_pull_requests,
        merged_pull_requests=service_stats.merged_pull_requests,
        assignments=service_stats.assignments,
        assignments_by_user=[
            AssignmentCountResponse(
                user_id=item.user_id,
                pull_requests=item.pull_requests,
            )
            for item in service_stats.assignments_by_user
        ],
        reviewers_by_pull_request=[
            PullRequestReviewersCountResponse(
                pull_request_id=item.pull_request_id,
                reviewers=item.reviewers,
            )
            for item in service_stats.reviewers_by_pull_request
        ],
    )


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return metrics_response()
