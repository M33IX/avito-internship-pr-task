class AppError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TeamAlreadyExistsError(AppError): ...


class TeamNotFoundError(AppError): ...


class UserNotFoundError(AppError): ...


class PullRequestAlreadyExistsError(AppError): ...


class PullRequestNotFoundError(AppError): ...


class PullRequestMergedError(AppError): ...


class ReviewerNotAssignedError(AppError): ...


class NoReviewerCandidateError(AppError): ...
