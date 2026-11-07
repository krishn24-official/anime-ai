"""Maps application errors to HTTP responses, so use cases never raise HTTPException."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.application.errors import InvalidInputError, NotFoundError

_STATUS_BY_ERROR = {
    NotFoundError: 404,
    InvalidInputError: 400,
}


def register_exception_handlers(app: FastAPI) -> None:
    for error_type, status_code in _STATUS_BY_ERROR.items():

        async def handler(_: Request, exc: Exception, status_code=status_code):
            return JSONResponse(status_code=status_code, content={"detail": exc.message})

        app.add_exception_handler(error_type, handler)
