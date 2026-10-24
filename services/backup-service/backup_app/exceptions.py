class ApplicationError(Exception):
    status_code = 400


class NotFoundError(ApplicationError):
    status_code = 404


class BackupFileNotFoundError(NotFoundError):
    pass


class ConflictError(ApplicationError):
    status_code = 409
