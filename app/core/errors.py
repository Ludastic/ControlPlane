from __future__ import annotations


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: object | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)
