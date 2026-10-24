"""The admin activity log: who changed what. Recording never makes the change itself fail."""

import logging

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.db import Base
from app.features.auth.models import User

logger = logging.getLogger(__name__)


class AdminAction(Base):
    __tablename__ = "admin_actions"

    action_id = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    admin_email = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    target = Column(Text)
    details = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def record(db: Session, admin: User, action: str, target: str | None = None, details: dict | None = None) -> None:
    """Write one line of the log (and commit it). Called after the change succeeded."""
    try:
        db.add(AdminAction(admin_user_id=admin.user_id, admin_email=admin.email, action=action, target=target, details=details or {}))
        db.commit()
    except SQLAlchemyError:
        logger.exception("Could not record the admin action %s", action)
        db.rollback()
