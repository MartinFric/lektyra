"""The one error the application raises on purpose. The API turns `code` into a status and shows `message` as is,
so a message is written for Martin, in plain words, and never carries a key, a path to data or a voice."""

from typing import Final, Literal

Code = Literal["not_found", "conflict", "invalid", "unavailable", "internal"]

STATUS: Final[dict[Code, int]] = {
    "not_found": 404,
    "conflict": 409,
    "invalid": 422,
    "unavailable": 503,
    "internal": 500,
}


class LektyraError(Exception):
    def __init__(self, code: Code, message: str) -> None:
        super().__init__(message)
        self.code: Code = code
        self.message = message
