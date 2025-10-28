from decimal import Decimal
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, func, Numeric, String, Integer, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    preferred_lang: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    recording: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    admin_left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    # New fields for Phase 1
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_login: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_participants: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    owner = relationship("User")

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), default="dev", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    room = relationship("Room")

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    room = relationship("Room")

class RoomCost(Base):
    __tablename__ = "room_costs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    room_id: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    pipeline: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(Text)
    units: Mapped[Optional[int]] = mapped_column(BigInteger)
    unit_type: Mapped[Optional[str]] = mapped_column(Text)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    segment_id: Mapped[Optional[int]] = mapped_column(Integer)

class RoomParticipant(Base):
    __tablename__ = "room_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    spoken_language: Mapped[str] = mapped_column(String(10), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    room = relationship("Room")
    user = relationship("User")

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False, unique=True)
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)  # free, plus, pro
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, cancelled, expired
    monthly_quota_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NULL means unlimited
    billing_period_start: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    billing_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", backref="subscription")

class UserUsage(Base):
    __tablename__ = "user_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    room_code: Mapped[str] = mapped_column(String(16), nullable=False)
    billing_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    stt_minutes: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    stt_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    mt_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    total_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")

    __table_args__ = (
        Index('ix_user_usage_billing_period', 'user_id', 'billing_period_start'),
    )

class RoomArchive(Base):
    __tablename__ = "room_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    recording: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_login: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_participants: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Aggregated metrics
    total_participants: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_minutes: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    stt_minutes: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    stt_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    mt_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    total_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)

    archive_reason: Mapped[str] = mapped_column(String(50), default="cleanup", nullable=False)

    owner = relationship("User")

class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
