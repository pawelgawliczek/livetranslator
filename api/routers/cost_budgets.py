"""Cost Budget Management API

Endpoints for admins to set and monitor cost budgets.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..models import User, CostBudget, BudgetAlert, RoomCost
from ..auth import get_current_user, get_db

router = APIRouter(prefix="/api", tags=["budgets"])


# Pydantic schemas
class BudgetCreateRequest(BaseModel):
    period_type: str = Field(default="monthly", pattern="^(monthly|weekly|daily)$")
    budget_usd: Decimal = Field(gt=0)
    alert_threshold_pct: int = Field(default=80, ge=0, le=100)
    critical_threshold_pct: int = Field(default=95, ge=0, le=100)


class BudgetUpdateRequest(BaseModel):
    budget_usd: Optional[Decimal] = Field(default=None, gt=0)
    alert_threshold_pct: Optional[int] = Field(default=None, ge=0, le=100)
    critical_threshold_pct: Optional[int] = Field(default=None, ge=0, le=100)
    is_active: Optional[bool] = None


class BudgetResponse(BaseModel):
    id: int
    period_type: str
    budget_usd: Decimal
    alert_threshold_pct: int
    critical_threshold_pct: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BudgetStatusResponse(BaseModel):
    budget: BudgetResponse
    current_period_start: datetime
    current_period_end: datetime
    current_cost_usd: Decimal
    percentage_used: int
    status: str  # 'ok', 'warning', 'critical', 'exceeded'
    projected_month_end_cost: Optional[Decimal] = None


class AlertResponse(BaseModel):
    id: int
    budget_id: int
    alert_type: str
    period_start: datetime
    period_end: datetime
    actual_cost_usd: Decimal
    budget_usd: Decimal
    percentage_used: int
    triggered_at: datetime
    acknowledged_at: Optional[datetime]


def get_period_bounds(period_type: str, now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """Calculate start and end of current period"""
    if now is None:
        now = datetime.utcnow()

    if period_type == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period_type == "weekly":
        # Week starts on Monday
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    else:  # monthly
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Next month first day
        if now.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

    return start, end


def calculate_current_cost(db: Session, start: datetime, end: datetime) -> Decimal:
    """Calculate total cost for period"""
    result = db.scalar(
        select(func.coalesce(func.sum(RoomCost.amount_usd), 0))
        .where(
            RoomCost.ts >= start,
            RoomCost.ts < end
        )
    )
    return Decimal(str(result)) if result else Decimal("0.00")


@router.get("/budgets", response_model=list[BudgetResponse])
async def list_budgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all cost budgets"""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")

    budgets = db.scalars(select(CostBudget).order_by(CostBudget.created_at.desc())).all()

    return [
        BudgetResponse(
            id=b.id,
            period_type=b.period_type,
            budget_usd=b.budget_usd,
            alert_threshold_pct=b.alert_threshold_pct,
            critical_threshold_pct=b.critical_threshold_pct,
            is_active=b.is_active,
            created_at=b.created_at,
            updated_at=b.updated_at
        )
        for b in budgets
    ]


@router.post("/budgets", response_model=BudgetResponse)
async def create_budget(
    request: BudgetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new cost budget"""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")

    # Check if active budget of same type exists
    existing = db.scalar(
        select(CostBudget).where(
            CostBudget.period_type == request.period_type,
            CostBudget.is_active == True
        )
    )

    if existing:
        raise HTTPException(400, f"Active {request.period_type} budget already exists")

    budget = CostBudget(
        period_type=request.period_type,
        budget_usd=request.budget_usd,
        alert_threshold_pct=request.alert_threshold_pct,
        critical_threshold_pct=request.critical_threshold_pct,
        updated_by=current_user.id
    )

    db.add(budget)
    db.commit()
    db.refresh(budget)

    return BudgetResponse(
        id=budget.id,
        period_type=budget.period_type,
        budget_usd=budget.budget_usd,
        alert_threshold_pct=budget.alert_threshold_pct,
        critical_threshold_pct=budget.critical_threshold_pct,
        is_active=budget.is_active,
        created_at=budget.created_at,
        updated_at=budget.updated_at
    )


@router.patch("/budgets/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: int,
    request: BudgetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing budget"""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")

    budget = db.get(CostBudget, budget_id)
    if not budget:
        raise HTTPException(404, "Budget not found")

    if request.budget_usd is not None:
        budget.budget_usd = request.budget_usd
    if request.alert_threshold_pct is not None:
        budget.alert_threshold_pct = request.alert_threshold_pct
    if request.critical_threshold_pct is not None:
        budget.critical_threshold_pct = request.critical_threshold_pct
    if request.is_active is not None:
        budget.is_active = request.is_active

    budget.updated_at = datetime.utcnow()
    budget.updated_by = current_user.id

    db.commit()
    db.refresh(budget)

    return BudgetResponse(
        id=budget.id,
        period_type=budget.period_type,
        budget_usd=budget.budget_usd,
        alert_threshold_pct=budget.alert_threshold_pct,
        critical_threshold_pct=budget.critical_threshold_pct,
        is_active=budget.is_active,
        created_at=budget.created_at,
        updated_at=budget.updated_at
    )


@router.delete("/budgets/{budget_id}")
async def delete_budget(
    budget_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a budget"""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")

    budget = db.get(CostBudget, budget_id)
    if not budget:
        raise HTTPException(404, "Budget not found")

    db.delete(budget)
    db.commit()

    return {"message": "Budget deleted successfully"}


@router.get("/budgets/{budget_id}/status", response_model=BudgetStatusResponse)
async def get_budget_status(
    budget_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current status of a budget including usage and alerts"""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")

    budget = db.get(CostBudget, budget_id)
    if not budget:
        raise HTTPException(404, "Budget not found")

    # Calculate current period
    period_start, period_end = get_period_bounds(budget.period_type)

    # Get current cost
    current_cost = calculate_current_cost(db, period_start, period_end)

    # Calculate percentage
    percentage_used = int((current_cost / budget.budget_usd) * 100) if budget.budget_usd > 0 else 0

    # Determine status
    if percentage_used >= 100:
        status = "exceeded"
    elif percentage_used >= budget.critical_threshold_pct:
        status = "critical"
    elif percentage_used >= budget.alert_threshold_pct:
        status = "warning"
    else:
        status = "ok"

    # Project month-end cost for monthly budgets
    projected_cost = None
    if budget.period_type == "monthly":
        now = datetime.utcnow()
        days_elapsed = (now - period_start).days + 1
        days_in_month = (period_end - period_start).days
        if days_elapsed > 0:
            projected_cost = (current_cost / Decimal(days_elapsed)) * Decimal(days_in_month)

    return BudgetStatusResponse(
        budget=BudgetResponse(
            id=budget.id,
            period_type=budget.period_type,
            budget_usd=budget.budget_usd,
            alert_threshold_pct=budget.alert_threshold_pct,
            critical_threshold_pct=budget.critical_threshold_pct,
            is_active=budget.is_active,
            created_at=budget.created_at,
            updated_at=budget.updated_at
        ),
        current_period_start=period_start,
        current_period_end=period_end,
        current_cost_usd=current_cost,
        percentage_used=percentage_used,
        status=status,
        projected_month_end_cost=projected_cost
    )


@router.get("/budgets/{budget_id}/alerts", response_model=list[AlertResponse])
async def get_budget_alerts(
    budget_id: int,
    limit: int = 50,
    acknowledged: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get alert history for a budget"""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")

    query = select(BudgetAlert).where(BudgetAlert.budget_id == budget_id)

    if acknowledged is not None:
        if acknowledged:
            query = query.where(BudgetAlert.acknowledged_at.isnot(None))
        else:
            query = query.where(BudgetAlert.acknowledged_at.is_(None))

    query = query.order_by(BudgetAlert.triggered_at.desc()).limit(limit)

    alerts = db.scalars(query).all()

    return [
        AlertResponse(
            id=a.id,
            budget_id=a.budget_id,
            alert_type=a.alert_type,
            period_start=a.period_start,
            period_end=a.period_end,
            actual_cost_usd=a.actual_cost_usd,
            budget_usd=a.budget_usd,
            percentage_used=a.percentage_used,
            triggered_at=a.triggered_at,
            acknowledged_at=a.acknowledged_at
        )
        for a in alerts
    ]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark an alert as acknowledged"""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")

    alert = db.get(BudgetAlert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")

    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = current_user.id

    db.commit()

    return {"message": "Alert acknowledged"}
