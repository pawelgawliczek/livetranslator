from decimal import Decimal
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, func, Numeric, String, Integer, Text, DateTime, Boolean, ForeignKey, Index, Float, JSON
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

    # Audio settings
    audio_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.02)
    preferred_mic_device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # TTS settings
    tts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tts_voice_preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tts_volume: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    tts_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    tts_pitch: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

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

    # Multi-speaker diarization fields
    discovery_mode: Mapped[str] = mapped_column(String(20), default="disabled", nullable=False)  # disabled, enabled, locked
    speakers_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # TTS settings
    tts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tts_voice_overrides: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    owner = relationship("User")
    speakers = relationship("RoomSpeaker", back_populates="room", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), default="dev", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    room = relationship("Room")

class RoomSpeaker(Base):
    __tablename__ = "room_speakers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True, nullable=False)
    speaker_id: Mapped[int] = mapped_column(Integer, nullable=False)  # Auto-assigned during discovery (0, 1, 2, ...)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)  # Hex color like #FF5733
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    room = relationship("Room", back_populates="speakers")

    __table_args__ = (
        Index('ix_room_speakers_room_speaker', 'room_id', 'speaker_id', unique=True),
    )

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True, nullable=False)
    segment_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False)
    src_lang: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Multi-speaker diarization field
    speaker_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)  # NULL for single-speaker mode

    room = relationship("Room")

class RoomCost(Base):
    __tablename__ = "room_costs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    room_id: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    pipeline: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(Text)
    units: Mapped[Optional[float]] = mapped_column(Numeric(12, 3))
    unit_type: Mapped[Optional[str]] = mapped_column(Text)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    segment_id: Mapped[Optional[int]] = mapped_column(Integer)

    # Multi-speaker cost tracking fields
    speaker_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Source speaker (NULL for single-speaker)
    target_speaker_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Target speaker (NULL for single-speaker)

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

    # Tier system quota tracking (Migration 016)
    quota_used_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_using_admin_quota: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quota_source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    room = relationship("Room")
    user = relationship("User")

class SubscriptionTier(Base):
    __tablename__ = "subscription_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tier_name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    monthly_price_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    monthly_quota_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    monthly_quota_messages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    features: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    provider_tier: Mapped[str] = mapped_column(String(20), default="standard", nullable=False)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    apple_product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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

    # Tier system extensions (Migration 016)
    tier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subscription_tiers.id"), nullable=True)
    bonus_credits_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grace_quota_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    apple_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    apple_transaction_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    apple_original_transaction_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user = relationship("User", backref="subscription")
    tier = relationship("SubscriptionTier")

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

class QuotaTransaction(Base):
    __tablename__ = "quota_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    room_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    quota_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_used: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    service_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transaction_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
    room = relationship("Room")

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    # Stripe fields
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Apple fields
    apple_transaction_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    apple_original_transaction_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    apple_product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    apple_receipt_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Common fields
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transaction_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user = relationship("User")

class CreditPackage(Base):
    __tablename__ = "credit_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    package_name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    price_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    apple_product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_room_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    admin = relationship("User", foreign_keys=[admin_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
    target_room = relationship("Room")

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[str] = mapped_column(String(20), nullable=False)
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    schedule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_in_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_dismissible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    creator = relationship("User", foreign_keys=[created_by])
    target_user = relationship("User", foreign_keys=[target_user_id])

class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    notification = relationship("Notification")
    user = relationship("User")
