from __future__ import annotations

import logging
from typing import Any, Protocol

from core.interfaces.logger import ILogger


class StdLoggerAdapter(ILogger):
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def debug(self, message: str, **context: Any) -> None:
        self._logger.debug(message, extra=context)

    def info(self, message: str, **context: Any) -> None:
        self._logger.info(message, extra=context)

    def warning(self, message: str, **context: Any) -> None:
        self._logger.warning(message, extra=context)

    def error(self, message: str, **context: Any) -> None:
        self._logger.error(message, extra=context)

    def exception(self, message: str, **context: Any) -> None:
        self._logger.exception(message, extra=context)


class LoguruLogger(Protocol):
    def bind(self, **kwargs: Any) -> LoguruLogger: ...

    def debug(self, message: str) -> None: ...

    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def exception(self, message: str) -> None: ...


class LoguruLoggerAdapter(ILogger):
    def __init__(self, logger: LoguruLogger) -> None:
        self._logger = logger

    def debug(self, message: str, **context: Any) -> None:
        self._logger.bind(**context).debug(message)

    def info(self, message: str, **context: Any) -> None:
        self._logger.bind(**context).info(message)

    def warning(self, message: str, **context: Any) -> None:
        self._logger.bind(**context).warning(message)

    def error(self, message: str, **context: Any) -> None:
        self._logger.bind(**context).error(message)

    def exception(self, message: str, **context: Any) -> None:
        self._logger.bind(**context).exception(message)
