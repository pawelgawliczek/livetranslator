"""
Admin API for credit package management and purchase history.

Security:
- All endpoints require admin authentication (require_admin dependency)
- Audit logging for all package edits
- Validation to prevent deactivating packages with recent purchases
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_, cast, Integer
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..db import SessionLocal
from ..models import User, CreditPackage, PaymentTransaction, QuotaTransaction, AdminAuditLog

router = APIRouter(prefix="/api/admin/credits", tags=["admin", "credits"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Request/Response Models
# ============================================================================

class CreditPackageUpdate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    hours: Decimal = Field(..., ge=0.01, le=100.00)
    price_usd: Decimal = Field(..., ge=0.01, le=999.99)
    sort_order: int = Field(..., ge=0, le=999)
    is_active: bool


class CreditPackageResponse(BaseModel):
    id: int
    package_name: str
    display_name: str
    hours: float
    price_usd: float
    discount_percent: float
    stripe_price_id: Optional[str]
    apple_product_id: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    purchase_count_30d: int


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/packages")
async def get_packages(
    include_inactive: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get all credit packages (admin view with purchase statistics).

    Query Parameters:
    - include_inactive: Include inactive packages. Default: false

    Returns:
    - packages: List of credit packages with 30-day purchase counts
    """
    # Build query with LEFT JOIN to get purchase counts
    # Use FILTER to count only completed purchases in last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    query = (
        select(
            CreditPackage,
            func.coalesce(
                func.count(PaymentTransaction.id).filter(
                    and_(
                        PaymentTransaction.created_at >= thirty_days_ago,
                        PaymentTransaction.status == 'completed',
                        or_(
                            PaymentTransaction.transaction_type == 'credit_purchase',
                            PaymentTransaction.transaction_type == 'credits'
                        )
                    )
                ),
                0
            ).label('purchase_count_30d')
        )
        .outerjoin(
            PaymentTransaction,
            cast(PaymentTransaction.transaction_metadata['package_id'], Integer) == CreditPackage.id
        )
        .group_by(CreditPackage.id)
    )

    if not include_inactive:
        query = query.where(CreditPackage.is_active == True)

    query = query.order_by(CreditPackage.sort_order, CreditPackage.id)

    results = db.execute(query).all()

    packages = []
    for pkg, purchase_count in results:
        packages.append({
            "id": pkg.id,
            "package_name": pkg.package_name,
            "display_name": pkg.display_name,
            "hours": float(pkg.hours),
            "price_usd": float(pkg.price_usd),
            "discount_percent": float(pkg.discount_percent),
            "stripe_price_id": pkg.stripe_price_id,
            "apple_product_id": pkg.apple_product_id,
            "is_active": pkg.is_active,
            "sort_order": pkg.sort_order,
            "created_at": pkg.created_at.isoformat(),
            "purchase_count_30d": purchase_count
        })

    return {"packages": packages}


@router.put("/packages/{id}")
async def update_package(
    id: int,
    request: CreditPackageUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    http_request: Request = None
):
    """
    Update credit package details.

    Validation:
    - display_name: 1-100 chars
    - hours: 0.01-100.00
    - price_usd: 0.01-999.99
    - sort_order: 0-999
    - Cannot deactivate if package has purchases in last 30 days (safety)

    Returns:
    - success: True
    - package: Updated package data
    - audit_log_id: ID of audit log entry
    """
    # 1. Fetch package
    package = db.get(CreditPackage, id)
    if not package:
        raise HTTPException(404, "Package not found")

    # 2. Check if trying to deactivate package with recent purchases
    if not request.is_active and package.is_active:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        purchase_count = db.scalar(
            select(func.count(PaymentTransaction.id))
            .where(
                and_(
                    cast(PaymentTransaction.transaction_metadata['package_id'], Integer) == package.id,
                    PaymentTransaction.created_at >= thirty_days_ago,
                    PaymentTransaction.status == 'completed',
                    or_(
                        PaymentTransaction.transaction_type == 'credit_purchase',
                        PaymentTransaction.transaction_type == 'credits'
                    )
                )
            )
        )

        if purchase_count > 0:
            raise HTTPException(
                400,
                f"Cannot deactivate package with {purchase_count} purchases in last 30 days. "
                "Wait until purchases are older than 30 days or contact system administrator."
            )

    # 3. Store old values for audit log
    old_values = {
        'display_name': package.display_name,
        'hours': float(package.hours),
        'price_usd': float(package.price_usd),
        'sort_order': package.sort_order,
        'is_active': package.is_active
    }

    # 4. Update package
    package.display_name = request.display_name
    package.hours = request.hours
    package.price_usd = request.price_usd
    package.sort_order = request.sort_order
    package.is_active = request.is_active

    # 5. Calculate discount percentage (base rate: $5/hour)
    base_cost = float(request.hours) * 5
    if base_cost > 0:
        discount = ((base_cost - float(request.price_usd)) / base_cost) * 100
        package.discount_percent = Decimal(max(0, discount))
    else:
        package.discount_percent = Decimal(0)

    db.commit()
    db.refresh(package)

    # 6. Create audit log
    audit_entry = AdminAuditLog(
        admin_id=current_user.id,
        action='update_credit_package',
        details={
            'package_id': package.id,
            'package_name': package.package_name,
            'old_values': old_values,
            'new_values': {
                'display_name': package.display_name,
                'hours': float(package.hours),
                'price_usd': float(package.price_usd),
                'sort_order': package.sort_order,
                'is_active': package.is_active
            }
        },
        ip_address=http_request.client.host if http_request else None,
        user_agent=http_request.headers.get('user-agent') if http_request else None
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)

    return {
        "success": True,
        "package": {
            "id": package.id,
            "package_name": package.package_name,
            "display_name": package.display_name,
            "hours": float(package.hours),
            "price_usd": float(package.price_usd),
            "discount_percent": float(package.discount_percent),
            "is_active": package.is_active,
            "sort_order": package.sort_order
        },
        "audit_log_id": audit_entry.id
    }


@router.get("/purchases")
async def get_purchases(
    user_email: Optional[str] = None,
    package: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get credit purchase history (admin view with filters).

    Query Parameters:
    - user_email: Filter by user email (partial match)
    - package: Filter by package name (1hr, 4hr, 8hr, 20hr)
    - start_date: Filter by start date (ISO timestamp)
    - end_date: Filter by end date (ISO timestamp)
    - platform: Filter by platform (stripe, apple)
    - status: Filter by status (pending, completed, failed, refunded)
    - limit: Results per page (max 5000). Default: 50
    - offset: Pagination offset. Default: 0

    Returns:
    - purchases: List of payment transactions
    - total: Total count (for pagination)
    - limit: Applied limit
    - offset: Applied offset
    """
    # Enforce max limit for CSV export
    if limit > 5000:
        limit = 5000

    # Build base query
    query = (
        select(PaymentTransaction)
        .join(User, PaymentTransaction.user_id == User.id)
        .outerjoin(
            CreditPackage,
            cast(PaymentTransaction.transaction_metadata['package_id'], Integer) == CreditPackage.id
        )
        .where(
            or_(
                PaymentTransaction.transaction_type == 'credit_purchase',
                PaymentTransaction.transaction_type == 'credits'
            )
        )
    )

    # Apply filters
    if user_email:
        query = query.where(User.email.ilike(f'%{user_email}%'))

    if package:
        query = query.where(CreditPackage.package_name == package)

    if start_date:
        query = query.where(PaymentTransaction.created_at >= start_date)

    if end_date:
        query = query.where(PaymentTransaction.created_at <= end_date)

    if platform:
        query = query.where(PaymentTransaction.platform == platform)

    if status:
        query = query.where(PaymentTransaction.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query)

    # Apply pagination
    query = query.order_by(PaymentTransaction.created_at.desc())
    query = query.limit(limit).offset(offset)

    transactions = db.scalars(query).all()

    # Build response
    purchases = []
    for tx in transactions:
        # Get user
        user = db.get(User, tx.user_id)

        # Get package info
        package_id = tx.transaction_metadata.get('package_id')
        package_name = None
        hours = None

        if package_id:
            pkg = db.get(CreditPackage, int(package_id))
            if pkg:
                package_name = pkg.package_name
                hours = float(pkg.hours)

        # Get quota transaction (if exists)
        quota_tx = db.scalar(
            select(QuotaTransaction)
            .where(
                and_(
                    QuotaTransaction.user_id == tx.user_id,
                    QuotaTransaction.transaction_type == 'purchase',
                    QuotaTransaction.transaction_metadata['payment_transaction_id'].as_string() == str(tx.id)
                )
            )
        )

        purchases.append({
            "id": tx.id,
            "user_id": tx.user_id,
            "user_email": user.email if user else "unknown",
            "package_id": package_id,
            "package_name": package_name,
            "hours": hours,
            "amount_usd": float(tx.amount_usd),
            "platform": tx.platform,
            "status": tx.status,
            "stripe_payment_intent_id": tx.stripe_payment_intent_id,
            "apple_transaction_id": tx.apple_transaction_id,
            "created_at": tx.created_at.isoformat(),
            "completed_at": tx.completed_at.isoformat() if tx.completed_at else None,
            "quota_transaction_id": quota_tx.id if quota_tx else None
        })

    return {
        "purchases": purchases,
        "total": total or 0,
        "limit": limit,
        "offset": offset
    }
