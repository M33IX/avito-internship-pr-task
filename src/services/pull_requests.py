from api.v1.pull_requests.schemas import (
    CreatePrRequest,
    CreatePrResponse,
    MergePrRequest,
    MergePrResponse,
    ReassignPrRequest,
    ReassignPrResponse,
)
from api.v1.pull_requests.schemas import (
    PullRequest as PullRequestSchema,
)
from core.application.use_cases import (
    CreatePullRequestCommand,
    MergePullRequestCommand,
    ReassignPullRequestReviewerCommand,
    create_pull_request,
    merge_pull_request,
    reassign_pull_request_reviewer,
)
from core.domain.entities import PullRequest
from core.interfaces.logger import ILogger
from core.interfaces.uow import IUnitOfWork


class PRService:
    def __init__(
        self,
        uow: IUnitOfWork,
        logger: ILogger,
    ) -> None:
        self._uow = uow
        self._logger = logger

    async def create_pr(self, request: CreatePrRequest) -> CreatePrResponse:
        pull_request = await create_pull_request(
            command=CreatePullRequestCommand(
                pull_request_id=request.pull_request_id,
                pull_request_name=request.pull_request_name,
                author_id=request.author_id,
            ),
            uow=self._uow,
            logger=self._logger,
        )
        return CreatePrResponse(pr=pull_request_to_schema(pull_request))

    async def merge_pr(self, request: MergePrRequest) -> MergePrResponse:
        pull_request = await merge_pull_request(
            command=MergePullRequestCommand(pull_request_id=request.pull_request_id),
            uow=self._uow,
            logger=self._logger,
        )
        return MergePrResponse(pr=pull_request_to_schema(pull_request))

    async def reassign_reviewer(
        self,
        request: ReassignPrRequest,
    ) -> ReassignPrResponse:
        result = await reassign_pull_request_reviewer(
            command=ReassignPullRequestReviewerCommand(
                pull_request_id=request.pull_request_id,
                old_user_id=request.old_user_id,
            ),
            uow=self._uow,
            logger=self._logger,
        )
        return ReassignPrResponse(
            pr=pull_request_to_schema(result.pull_request),
            replaced_by=result.replaced_by,
        )


def pull_request_to_schema(pull_request: PullRequest) -> PullRequestSchema:
    return PullRequestSchema(
        pull_request_id=pull_request.pull_request_id,
        pull_request_name=pull_request.pull_request_name,
        author_id=pull_request.author_id,
        status=pull_request.status,
        assigned_reviewers=pull_request.assigned_reviewers,
        createdAt=pull_request.created_at,
        mergedAt=pull_request.merged_at,
    )
