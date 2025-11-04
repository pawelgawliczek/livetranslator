"""
Admin Audit Log Router
Provides endpoints for viewing and exporting admin action audit logs.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, and_, desc
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
import csv
import io
import json

from ..db import get_db
from ..models import AdminAuditLog, User
from ..auth import require_admin

router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin-audit"])


# Pydantic models
class AdminUserInfo(BaseModel):
    id: int
    email: str
    display_name: str

    class Config:
        from_attributes = True


class TargetUserInfo(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True


class AuditLogEntry(BaseModel):
    id: int
    timestamp: datetime
    admin: AdminUserInfo
    action: str
    target_user: Optional[TargetUserInfo]
    target_room_id: Optional[int]
    details: dict
    ip_address: Optional[str]
    user_agent: Optional[str]

    class Config:
        from_attributes = True


class AuditLogsResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
    limit: int
    offset: int


@router.get("", response_model=AuditLogsResponse)
def get_audit_logs(
    start_date: Optional[str] = Query(None, description="ISO 8601 start date"),
    end_date: Optional[str] = Query(None, description="ISO 8601 end date"),
    admin_id: Optional[int] = Query(None, description="Filter by admin user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    target_user_id: Optional[int] = Query(None, description="Filter by target user ID"),
    limit: int = Query(50, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of audit logs with optional filters.
    Admin-only access.
    """
    # Build query with eager loading
    query = (
        select(AdminAuditLog)
        .options(
            joinedload(AdminAuditLog.admin),
            joinedload(AdminAuditLog.target_user)
        )
        .order_by(desc(AdminAuditLog.created_at))
    )

    # Apply filters
    filters = []

    # Default to last 30 days if no dates provided
    if not start_date and not end_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            filters.append(AdminAuditLog.created_at >= start_dt)
        except ValueError:
            pass  # Invalid date, skip filter

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filters.append(AdminAuditLog.created_at <= end_dt)
        except ValueError:
            pass  # Invalid date, skip filter

    if admin_id:
        filters.append(AdminAuditLog.admin_id == admin_id)

    if action:
        filters.append(AdminAuditLog.action == action)

    if target_user_id:
        filters.append(AdminAuditLog.target_user_id == target_user_id)

    if filters:
        query = query.where(and_(*filters))

    # Get total count
    count_query = select(func.count()).select_from(AdminAuditLog)
    if filters:
        count_query = count_query.where(and_(*filters))
    total = db.scalar(count_query) or 0

    # Get paginated results
    logs = db.scalars(query.limit(limit).offset(offset)).unique().all()

    # Convert to response format
    log_entries = []
    for log in logs:
        entry = AuditLogEntry(
            id=log.id,
            timestamp=log.created_at,
            admin=AdminUserInfo(
                id=log.admin.id,
                email=log.admin.email,
                display_name=log.admin.display_name
            ) if log.admin else AdminUserInfo(
                id=log.admin_id,
                email="DELETED",
                display_name="Deleted Admin"
            ),
            action=log.action,
            target_user=TargetUserInfo(
                id=log.target_user.id,
                email=log.target_user.email
            ) if log.target_user else None,
            target_room_id=log.target_room_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent
        )
        log_entries.append(entry)

    return AuditLogsResponse(
        logs=log_entries,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/export")
def export_audit_logs(
    start_date: Optional[str] = Query(None, description="ISO 8601 start date"),
    end_date: Optional[str] = Query(None, description="ISO 8601 end date"),
    admin_id: Optional[int] = Query(None, description="Filter by admin user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    target_user_id: Optional[int] = Query(None, description="Filter by target user ID"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Export audit logs as CSV file (max 10,000 rows).
    Admin-only access.
    """
    # Build query (reuse logic from get_audit_logs)
    query = (
        select(AdminAuditLog)
        .options(
            joinedload(AdminAuditLog.admin),
            joinedload(AdminAuditLog.target_user)
        )
        .order_by(desc(AdminAuditLog.created_at))
    )

    # Apply filters
    filters = []

    # Default to last 30 days if no dates provided
    if not start_date and not end_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            filters.append(AdminAuditLog.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filters.append(AdminAuditLog.created_at <= end_dt)
        except ValueError:
            pass

    if admin_id:
        filters.append(AdminAuditLog.admin_id == admin_id)

    if action:
        filters.append(AdminAuditLog.action == action)

    if target_user_id:
        filters.append(AdminAuditLog.target_user_id == target_user_id)

    if filters:
        query = query.where(and_(*filters))

    # Limit to 10,000 rows
    logs = db.scalars(query.limit(10000)).unique().all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'timestamp',
        'admin_email',
        'admin_display_name',
        'action',
        'target_user_email',
        'target_room_id',
        'ip_address',
        'details_json'
    ])

    # Write rows
    for log in logs:
        writer.writerow([
            log.created_at.isoformat() if log.created_at else '',
            log.admin.email if log.admin else 'DELETED',
            log.admin.display_name if log.admin else '',
            log.action,
            log.target_user.email if log.target_user else '',
            log.target_room_id or '',
            log.ip_address or '',
            json.dumps(log.details)
        ])

    # Prepare file for download
    output.seek(0)
    filename = f"audit_log_{datetime.now().strftime('%Y-%m-%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/admins")
def get_admin_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get list of admin users for filter dropdown.
    Admin-only access.
    """
    admins = db.scalars(
        select(User)
        .where(User.is_admin == True)
        .order_by(User.email)
    ).all()

    return {
        "admins": [
            {
                "id": a.id,
                "email": a.email,
                "display_name": a.display_name
            }
            for a in admins
        ]
    }
