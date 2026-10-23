import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from requests.exceptions import ConnectionError, Timeout

from verification_app.exceptions import ApplicationError
from verification_app.restore import DockerUnavailableError

logger = logging.getLogger(__name__)


async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


async def database_unavailable_handler(request: Request, exc: OperationalError) -> JSONResponse:
    logger.error("Database request failed: %s %s", request.method, request.url.path,
                 exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled request error: %s %s", request.method, request.url.path,
                 exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


async def verification_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Verification unavailable", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=503, content={"detail": "Verification service temporarily unavailable"})


async def verification_timeout_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Verification timed out", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=504, content={"detail": "Verification timed out"})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(OperationalError, database_unavailable_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.add_exception_handler(DockerUnavailableError, verification_unavailable_handler)
    app.add_exception_handler(ConnectionError, verification_unavailable_handler)
    app.add_exception_handler(Timeout, verification_timeout_handler)
    app.add_exception_handler(TimeoutError, verification_timeout_handler)
