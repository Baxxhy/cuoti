from datetime import datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel


class Envelope(BaseModel):
    success: bool = True
    data: Any
    error: None = None
    request_id: str


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def envelope(request, data):
    value = Envelope(data=data, request_id=request.state.request_id).model_dump()
    return jsonable_encoder(
        value, custom_encoder={datetime: lambda item: item.isoformat()}
    )
