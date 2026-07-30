# Destination in repo: backend/app/core/exceptions.py
# The FastAPI handler at the bottom of this file goes in main.py
# (shown here together for review; split when you copy it in).

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base class for all domain-level exceptions.

    `detail` is internal — safe to log, never serialized to the client.
    `user_message` is what the client actually sees. Keeping these as two
    separate attributes (rather than one string doing both jobs) is the
    same principle already locked in ARCHITECTURE.md §6 for
    ContactProvider's error_message vs. ContactDiscoveryResponse.fallback_reason
    — this class just makes that pattern reusable across every router,
    not only the discovery pipeline.

    Routers and services raise a subclass of this; they never construct
    HTTPException directly. Only the exception handler below does that
    translation, in exactly one place.
    """

    status_code: int = 500
    default_user_message: str = "Something went wrong. Please try again."

    def __init__(self, detail: str, user_message: str | None = None):
        self.detail = detail
        self.user_message = user_message or self.default_user_message
        super().__init__(detail)


class NotFoundError(AppException):
    status_code = 404
    default_user_message = "The requested resource was not found."


class AuthenticationError(AppException):
    status_code = 401
    default_user_message = "Could not validate credentials."


class AuthorizationError(AppException):
    status_code = 403
    default_user_message = "You don't have permission to do that."


class ValidationError(AppException):
    status_code = 422
    default_user_message = "The provided data was invalid."


class ConflictError(AppException):
    status_code = 409
    default_user_message = "A conflicting resource already exists."


class ProviderUnavailableError(AppException):
    """For contact_discovery.py's own genuinely-unexpected failures only —
    NOT for routine rate-limit/timeout handling, which stays inside
    ProviderSearchResult.status per ARCHITECTURE.md §4.1. If you find
    yourself raising this from inside a ContactProvider implementation,
    that's a sign the status-object boundary is being violated.
    """

    status_code = 502
    default_user_message = (
        "One of our contact-data providers is temporarily unavailable."
    )


# --- Registration (goes in main.py, not exceptions.py, in the real repo) ---

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        # TODO: replace with real logging (structlog / stdlib logging) —
        # exc.detail is the only place the internal detail is allowed to surface.
        print(f"[AppException] {exc.__class__.__name__}: {exc.detail}")

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "user_message": exc.user_message,
                "error_code": exc.__class__.__name__,
            },
        )
