"""Idempotency receipts for precise offline draft writes; no duplicate learning record."""
from datetime import datetime
from sqlalchemy import String, JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class OfflineOperation(Base):
    __tablename__='offline_operations'
    owner_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'),primary_key=True)
    operation_id:Mapped[str]=mapped_column(String(64),primary_key=True)
    request_hash:Mapped[str]=mapped_column(String(64))
    result:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
