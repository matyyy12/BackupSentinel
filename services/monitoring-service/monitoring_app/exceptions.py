class ApplicationError(Exception):
    """An expected error with a message safe to expose through the API."""
    status_code = 400


class NotFoundError(ApplicationError):
    status_code = 404
