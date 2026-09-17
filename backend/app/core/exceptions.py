from fastapi import HTTPException, status

class BaseAPIException(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(
            status_code=status_code,
            detail={"success": False, "error": {"code": code, "message": message}}
        )

class NotFoundException(BaseAPIException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, "NOT_FOUND", message)

class UnauthorizedException(BaseAPIException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", message)

class ForbiddenException(BaseAPIException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(status.HTTP_403_FORBIDDEN, "FORBIDDEN", message)

class BadRequestException(BaseAPIException):
    def __init__(self, message: str = "Bad Request"):
        super().__init__(status.HTTP_400_BAD_REQUEST, "BAD_REQUEST", message)

class ConflictException(BaseAPIException):
    def __init__(self, message: str = "Conflict"):
        super().__init__(status.HTTP_409_CONFLICT, "CONFLICT", message)

class ServiceUnavailableException(BaseAPIException):
    def __init__(self, message: str = "Service Unavailable"):
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE", message)

