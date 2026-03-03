"""Notification Management API - Admin and User endpoints (Basic version without WebSocket)"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text, and_, or_
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import logging

from ..auth import require_admin, get_optional_current_user, get_db
from ..models import User, Notification, NotificationDelivery

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])

# Rate limiting: track last notification creation time per admin
_admin_notification_timestamps: Dict[int, datetime] = {}
RATE_LIMIT_SECONDS = 60

# ============================================================================
# Pydantic Models
# ============================================================================

class CreateNotificationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=500)
    type: str = Field(..., pattern="^(info|warning|success|error)$")
    target: str = Field(..., pattern="^(all|free|plus|pro|individual)$")
    target_user_id: Optional[int] = None
    schedule_type: str = Field(..., pattern="^(immediate|scheduled)$")
    scheduled_for: Optional[datetime] = None
    expires_in_seconds: Optional[int] = Field(None, ge=0, le=2592000)  # Max 30 days
    is_dismissible: bool = True

    @field_validator('scheduled_for')
    @classmethod
    def validate_scheduled_for(cls, v, info):
        schedule_type = info.data.get('schedule_type')
        if schedule_type == 'scheduled':
            if v is None:
                raise ValueError('scheduled_for is required when schedule_type is scheduled')
            if v <= datetime.utcnow():
                raise ValueError('scheduled_for must be in the future')
        return v

    @field_validator('target_user_id')
    @classmethod
    def validate_target_user_id(cls, v, info):
        target = info.data.get('target')
        if target == 'individual':
            if v is None:
                raise ValueError('target_user_id is required when target is individual')
        return v


class UpdateNotificationRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    message: Optional[str] = Field(None, min_length=1, max_length=500)
    type: Optional[str] = Field(None, pattern="^(info|warning|success|error)$")
    scheduled_for: Optional[datetime] = None
    expires_in_seconds: Optional[int] = Field(None, ge=0, le=2592000)
    is_dismissible: Optional[bool] = None


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    target: str
    status: str
    scheduled_for: Optional[datetime] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    delivered_count: int
    target_count: int
    created_by_email: str

    class Config:
        from_attributes = True


class UserNotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    is_dismissible: bool
    delivered_at: datetime
    read_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# Helper Functions
# ============================================================================

def _create_deliveries(notification_id: int, target: str, target_user_id: Optional[int], db: Session) -> int:
    """Create delivery records for notification (synchronous, no WebSocket)"""
    try:
        # Get target user IDs based on notification.target
        target_user_ids = _get_target_user_ids(target, target_user_id, db)

        if not target_user_ids:
            logger.warning(f"No target users found for notification {notification_id}")
            return 0

        # Create delivery records (batch insert for performance)
        deliveries = []
        for user_id in target_user_ids:
            # Check if delivery already exists (idempotent)
            existing = db.scalar(
                select(NotificationDelivery)
                .where(
                    and_(
                        NotificationDelivery.notification_id == notification_id,
                        NotificationDelivery.user_id == user_id
                    )
                )
            )
            if not existing:
                deliveries.append(NotificationDelivery(
                    notification_id=notification_id,
                    user_id=user_id,
                    delivered_at=datetime.utcnow()
                ))

        if deliveries:
            db.add_all(deliveries)
            db.commit()

        logger.info(f"Created {len(deliveries)} delivery records for notification {notification_id}")
        return len(deliveries)

    except Exception as e:
        logger.error(f"Failed to create deliveries for notification {notification_id}: {e}")
        return 0


def _get_target_user_ids(target: str, target_user_id: Optional[int], db: Session) -> List[int]:
    """Get list of user IDs based on target criteria"""
    if target == "individual":
        return [target_user_id] if target_user_id else []

    elif target == "all":
        # All users
        result = db.execute(select(User.id))
        return [row[0] for row in result.fetchall()]

    else:
        # Tier-based targeting no longer supported (billing removed)
        # Fall back to all users
        result = db.execute(select(User.id))
        return [row[0] for row in result.fetchall()]


def _calculate_target_count(target: str, target_user_id: Optional[int], db: Session) -> int:
    """Calculate expected target user count"""
    if target == "individual":
        return 1 if target_user_id else 0

    elif target == "all":
        return db.scalar(select(func.count(User.id))) or 0

    else:
        # Tier-based count no longer supported (billing removed)
        # Fall back to all users count
        return db.scalar(select(func.count(User.id))) or 0


def _check_rate_limit(admin_id: int) -> bool:
    """Check if admin has exceeded rate limit (1 notification per minute)"""
    last_time = _admin_notification_timestamps.get(admin_id)
    if last_time:
        elapsed = (datetime.utcnow() - last_time).total_seconds()
        if elapsed < RATE_LIMIT_SECONDS:
            return False
    return True


def _update_rate_limit(admin_id: int):
    """Update rate limit timestamp for admin"""
    _admin_notification_timestamps[admin_id] = datetime.utcnow()


# ============================================================================
# Admin Endpoints
# ============================================================================

@router.post("/api/admin/notifications", status_code=201)
def create_notification(
    req: CreateNotificationRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new notification (basic version without WebSocket)"""

    # Rate limiting
    if not _check_rate_limit(admin.id):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please wait {RATE_LIMIT_SECONDS} seconds between notifications."
        )

    # Validate target_user_id exists if individual target
    if req.target == "individual" and req.target_user_id:
        target_user = db.get(User, req.target_user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")

    # Create notification
    notification = Notification(
        title=req.title,
        message=req.message,
        type=req.type,
        target=req.target,
        target_user_id=req.target_user_id,
        schedule_type=req.schedule_type,
        scheduled_for=req.scheduled_for,
        expires_in_seconds=req.expires_in_seconds,
        is_dismissible=req.is_dismissible,
        status="scheduled" if req.schedule_type == "scheduled" else "draft",
        created_by=admin.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    # Update rate limit
    _update_rate_limit(admin.id)

    # Calculate target count
    target_count = _calculate_target_count(req.target, req.target_user_id, db)

    # If immediate, send now (create delivery records)
    delivered_count = 0
    if req.schedule_type == "immediate":
        notification.status = "sent"
        notification.sent_at = datetime.utcnow()
        db.commit()

        # Create delivery records synchronously
        delivered_count = _create_deliveries(notification.id, req.target, req.target_user_id, db)

    return {
        "notification_id": notification.id,
        "status": notification.status,
        "scheduled_for": notification.scheduled_for.isoformat() if notification.scheduled_for else None,
        "target_user_count": target_count,
        "delivered_count": delivered_count,
        "message": f"Notification {'scheduled' if req.schedule_type == 'scheduled' else 'sent'} successfully"
    }


@router.get("/api/admin/notifications")
def list_notifications(
    type: Optional[str] = Query(None, pattern="^(info|warning|success|error)$"),
    target: Optional[str] = Query(None, pattern="^(all|free|plus|pro|individual)$"),
    status: Optional[str] = Query(None, pattern="^(draft|scheduled|sent|expired|cancelled)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all notifications with filters"""

    # Build query
    query = select(Notification).order_by(Notification.created_at.desc())

    # Apply filters
    if type:
        query = query.where(Notification.type == type)
    if target:
        query = query.where(Notification.target == target)
    if status:
        query = query.where(Notification.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Apply pagination
    query = query.limit(limit).offset(offset)
    notifications = db.scalars(query).all()

    # Build response with delivery stats
    result = []
    for n in notifications:
        # Get delivered count
        delivered_count = db.scalar(
            select(func.count(NotificationDelivery.id))
            .where(NotificationDelivery.notification_id == n.id)
        ) or 0

        # Calculate target count
        target_count = _calculate_target_count(n.target, n.target_user_id, db)

        # Get creator email
        creator = db.get(User, n.created_by)

        result.append({
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "target": n.target,
            "status": n.status,
            "scheduled_for": n.scheduled_for.isoformat() if n.scheduled_for else None,
            "created_at": n.created_at.isoformat(),
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "delivered_count": delivered_count,
            "target_count": target_count,
            "created_by_email": creator.email if creator else "unknown"
        })

    return {
        "notifications": result,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/api/admin/notifications/{notification_id}")
def get_notification_detail(
    notification_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get notification details with delivery breakdown"""

    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Calculate expires_at
    expires_at = None
    if notification.sent_at and notification.expires_in_seconds:
        expires_at = notification.sent_at + timedelta(seconds=notification.expires_in_seconds)

    # Get delivery stats
    total_delivered = db.scalar(
        select(func.count(NotificationDelivery.id))
        .where(NotificationDelivery.notification_id == notification_id)
    ) or 0

    total_read = db.scalar(
        select(func.count(NotificationDelivery.id))
        .where(
            and_(
                NotificationDelivery.notification_id == notification_id,
                NotificationDelivery.read_at.isnot(None)
            )
        )
    ) or 0

    total_dismissed = db.scalar(
        select(func.count(NotificationDelivery.id))
        .where(
            and_(
                NotificationDelivery.notification_id == notification_id,
                NotificationDelivery.dismissed_at.isnot(None)
            )
        )
    ) or 0

    target_count = _calculate_target_count(notification.target, notification.target_user_id, db)

    # Delivery breakdown (tier-based breakdown removed with billing)
    delivery_breakdown = {}

    return {
        "notification": {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "type": notification.type,
            "target": notification.target,
            "status": notification.status,
            "created_at": notification.created_at.isoformat(),
            "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
            "expires_at": expires_at.isoformat() if expires_at else None
        },
        "delivery_stats": {
            "total_delivered": total_delivered,
            "total_read": total_read,
            "total_dismissed": total_dismissed,
            "target_count": target_count
        },
        "delivery_breakdown": delivery_breakdown
    }


@router.put("/api/admin/notifications/{notification_id}")
def update_notification(
    notification_id: int,
    req: UpdateNotificationRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a notification (only draft or scheduled)"""

    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Can only edit draft or scheduled notifications
    if notification.status not in ["draft", "scheduled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit notification with status '{notification.status}'"
        )

    # Update fields
    if req.title is not None:
        notification.title = req.title
    if req.message is not None:
        notification.message = req.message
    if req.type is not None:
        notification.type = req.type
    if req.scheduled_for is not None:
        if req.scheduled_for <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="scheduled_for must be in the future")
        notification.scheduled_for = req.scheduled_for
    if req.expires_in_seconds is not None:
        notification.expires_in_seconds = req.expires_in_seconds
    if req.is_dismissible is not None:
        notification.is_dismissible = req.is_dismissible

    notification.updated_at = datetime.utcnow()
    db.commit()

    return {
        "notification_id": notification.id,
        "message": "Notification updated successfully"
    }


@router.delete("/api/admin/notifications/{notification_id}")
def cancel_notification(
    notification_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Cancel a notification (only draft or scheduled)"""

    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Can only cancel draft or scheduled notifications
    if notification.status not in ["draft", "scheduled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel notification with status '{notification.status}'"
        )

    notification.status = "cancelled"
    notification.updated_at = datetime.utcnow()
    db.commit()

    return {
        "notification_id": notification.id,
        "message": "Notification cancelled successfully"
    }


# ============================================================================
# User Endpoints
# ============================================================================

@router.get("/api/notifications")
def get_user_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(10, ge=1, le=50),
    user_dict: Optional[dict] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """Get user's notifications"""

    if not user_dict:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Get user from database (user_dict is JWT payload with 'sub' key)
    user_id = int(user_dict.get("sub"))
    user = db.get(User, user_id)

    # Build query - get user's deliveries
    query = (
        select(NotificationDelivery, Notification)
        .join(Notification, NotificationDelivery.notification_id == Notification.id)
        .where(NotificationDelivery.user_id == user.id)
        .order_by(NotificationDelivery.delivered_at.desc())
    )

    # Filter unread only
    if unread_only:
        query = query.where(NotificationDelivery.dismissed_at.is_(None))

    # Filter out expired notifications
    now = datetime.utcnow()
    query = query.where(
        or_(
            Notification.expires_in_seconds.is_(None),
            Notification.sent_at.is_(None),
            Notification.sent_at + text(f"INTERVAL '1 second' * notifications.expires_in_seconds") > now
        )
    )

    # Apply limit
    query = query.limit(limit)

    results = db.execute(query).all()

    # Build response
    notifications = []
    for delivery, notification in results:
        expires_at = None
        if notification.sent_at and notification.expires_in_seconds:
            expires_at = notification.sent_at + timedelta(seconds=notification.expires_in_seconds)

        notifications.append({
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "type": notification.type,
            "is_dismissible": notification.is_dismissible,
            "delivered_at": delivery.delivered_at.isoformat(),
            "read_at": delivery.read_at.isoformat() if delivery.read_at else None,
            "dismissed_at": delivery.dismissed_at.isoformat() if delivery.dismissed_at else None,
            "expires_at": expires_at.isoformat() if expires_at else None
        })

    # Get unread count
    unread_count = db.scalar(
        select(func.count(NotificationDelivery.id))
        .join(Notification, NotificationDelivery.notification_id == Notification.id)
        .where(
            and_(
                NotificationDelivery.user_id == user.id,
                NotificationDelivery.dismissed_at.is_(None),
                or_(
                    Notification.expires_in_seconds.is_(None),
                    Notification.sent_at.is_(None),
                    Notification.sent_at + text(f"INTERVAL '1 second' * notifications.expires_in_seconds") > now
                )
            )
        )
    ) or 0

    return {
        "notifications": notifications,
        "unread_count": unread_count
    }


@router.post("/api/notifications/{notification_id}/dismiss")
def dismiss_notification(
    notification_id: int,
    user_dict: Optional[dict] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """Dismiss a notification"""

    if not user_dict:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = int(user_dict.get("sub"))

    # Get delivery record
    delivery = db.scalar(
        select(NotificationDelivery)
        .where(
            and_(
                NotificationDelivery.notification_id == notification_id,
                NotificationDelivery.user_id == user_id
            )
        )
    )

    if not delivery:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Update dismissed_at
    delivery.dismissed_at = datetime.utcnow()
    db.commit()

    return {"message": "Notification dismissed"}


@router.post("/api/notifications/{notification_id}/mark-read")
def mark_notification_read(
    notification_id: int,
    user_dict: Optional[dict] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """Mark notification as read"""

    if not user_dict:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = int(user_dict.get("sub"))

    # Get delivery record
    delivery = db.scalar(
        select(NotificationDelivery)
        .where(
            and_(
                NotificationDelivery.notification_id == notification_id,
                NotificationDelivery.user_id == user_id
            )
        )
    )

    if not delivery:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Update read_at (only if not already set)
    if not delivery.read_at:
        delivery.read_at = datetime.utcnow()
        db.commit()

    return {"message": "Notification marked as read"}
