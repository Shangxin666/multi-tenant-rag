import logging
import traceback

logger = logging.getLogger("app.ingestion")


class IngestionError(Exception):
    """Only fixed, safe summaries may be passed to this exception."""


class UploadError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def log_failure(stage: str, error: BaseException) -> None:
    # Retain stack locations, never exception text or captured locals/file content.
    frames = "".join(traceback.format_list(traceback.extract_tb(error.__traceback__)))
    logger.error("%s: %s\n%s", stage, type(error).__name__, frames)
