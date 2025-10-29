"""Admin Cost Analytics API - Comprehensive provider cost tracking and analysis"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from ..auth import require_admin, get_db
from ..models import User

router = APIRouter(prefix="/api/admin/costs", tags=["admin-costs"])


# ============================================================================
# Pydantic Models
# ============================================================================

class PeriodInfo(BaseModel):
    start: datetime
    end: datetime
    granularity: str


class ProviderBreakdown(BaseModel):
    cost_usd: float
    units: float
    unit_type: str
    percentage: float


class TotalsInfo(BaseModel):
    cost_usd: float
    stt_cost_usd: float
    mt_cost_usd: float
    total_minutes: float
    total_hours: float
    active_users: int
    active_rooms: int
    growth_rate: Optional[float] = None


class OverviewResponse(BaseModel):
    period: PeriodInfo
    totals: TotalsInfo
    stt_breakdown: Dict[str, ProviderBreakdown]
    mt_breakdown: Dict[str, ProviderBreakdown]


class TimeSeriesDataPoint(BaseModel):
    timestamp: datetime
    total_cost_usd: float
    stt_cost_usd: float
    mt_cost_usd: float
    event_count: int
    accumulated_cost_usd: Optional[float] = None
    accumulated_stt_cost_usd: Optional[float] = None
    accumulated_mt_cost_usd: Optional[float] = None
    providers: Optional[Dict[str, Dict[str, float]]] = None


class TimeSeriesResponse(BaseModel):
    granularity: str
    accumulated: bool
    by_provider: bool
    data: List[TimeSeriesDataPoint]


class UserSummary(BaseModel):
    user_id: int
    email: str
    display_name: str
    room_count: int
    stt_cost_usd: float
    stt_minutes: float
    mt_cost_usd: float
    mt_tokens: Optional[float]
    mt_characters: Optional[float]
    total_cost_usd: float
    top_stt_provider: Optional[str]
    top_mt_provider: Optional[str]


class PageInfo(BaseModel):
    limit: int
    offset: int
    has_more: bool


class UsersResponse(BaseModel):
    total_users: int
    page: PageInfo
    users: List[UserSummary]


class RoomSummary(BaseModel):
    room_id: int
    room_code: str
    is_public: bool
    owner: Dict[str, Any]
    created_at: datetime
    stt_cost_usd: float
    stt_minutes: float
    mt_cost_usd: float
    total_cost_usd: float


class RoomsResponse(BaseModel):
    total_rooms: int
    page: PageInfo
    rooms: List[RoomSummary]


# ============================================================================
# Helper Functions
# ============================================================================

def auto_detect_granularity(start_date: datetime, end_date: datetime) -> str:
    """Auto-detect appropriate granularity based on date range"""
    delta = end_date - start_date
    hours = delta.total_seconds() / 3600
    days = hours / 24

    if hours <= 48:
        return 'hour'
    elif days <= 60:
        return 'day'
    elif days <= 365:
        return 'week'
    elif days <= 730:
        return 'month'
    else:
        return 'year'


def calculate_growth_rate(db: Session, start_date: datetime, end_date: datetime, current_cost: float) -> Optional[float]:
    """Calculate cost growth rate compared to previous period"""
    try:
        period_duration = end_date - start_date
        previous_start = start_date - period_duration
        previous_end = start_date

        query = text("""
            SELECT COALESCE(SUM(amount_usd), 0) as total_cost
            FROM room_costs
            WHERE ts >= :start_date AND ts < :end_date
        """)

        result = db.execute(query, {
            "start_date": previous_start,
            "end_date": previous_end
        }).fetchone()

        previous_cost = float(result[0]) if result else 0.0

        if previous_cost > 0:
            return ((current_cost - previous_cost) / previous_cost) * 100
        return None
    except Exception as e:
        print(f"[Admin Costs] Error calculating growth rate: {e}")
        return None


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/overview")
async def get_cost_overview(
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    granularity: Optional[str] = Query(None, description="hour|day|week|month|year"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get system-wide cost overview with provider breakdown.

    Returns total costs, STT/MT breakdown, usage metrics, and provider details.
    """

    # Auto-detect granularity if not provided
    if not granularity:
        granularity = auto_detect_granularity(start_date, end_date)

    # Get total costs
    totals_query = text("""
        SELECT
            COALESCE(SUM(amount_usd), 0) as total_cost,
            COALESCE(SUM(CASE WHEN pipeline = 'stt' THEN amount_usd ELSE 0 END), 0) as stt_cost,
            COALESCE(SUM(CASE WHEN pipeline = 'mt' THEN amount_usd ELSE 0 END), 0) as mt_cost,
            COALESCE(SUM(CASE WHEN pipeline = 'stt' AND unit_type = 'seconds' THEN units ELSE 0 END), 0) / 60.0 as total_minutes,
            COUNT(DISTINCT room_id) as active_rooms
        FROM room_costs
        WHERE ts >= :start_date AND ts <= :end_date
    """)

    totals = db.execute(totals_query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchone()

    total_cost = float(totals[0])
    stt_cost = float(totals[1])
    mt_cost = float(totals[2])
    total_minutes = float(totals[3])
    active_rooms = int(totals[4])

    # Get active users count (users who created rooms with activity)
    users_query = text("""
        SELECT COUNT(DISTINCT r.owner_id)
        FROM room_costs rc
        JOIN rooms r ON rc.room_id = r.code
        WHERE rc.ts >= :start_date AND rc.ts <= :end_date
    """)

    active_users = db.execute(users_query, {
        "start_date": start_date,
        "end_date": end_date
    }).scalar() or 0

    # Calculate growth rate
    growth_rate = calculate_growth_rate(db, start_date, end_date, total_cost)

    # Get STT provider breakdown
    stt_breakdown_query = text("""
        SELECT
            provider,
            SUM(amount_usd) as cost_usd,
            SUM(units) as units,
            unit_type
        FROM room_costs
        WHERE ts >= :start_date
          AND ts <= :end_date
          AND pipeline = 'stt'
          AND provider IS NOT NULL
        GROUP BY provider, unit_type
        ORDER BY cost_usd DESC
    """)

    stt_results = db.execute(stt_breakdown_query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()

    stt_breakdown = {}
    for row in stt_results:
        provider = row[0]
        cost = float(row[1])
        units = float(row[2]) if row[2] else 0.0
        unit_type = row[3]
        percentage = (cost / stt_cost * 100) if stt_cost > 0 else 0.0

        stt_breakdown[provider] = {
            "cost_usd": cost,
            "units": units,
            "unit_type": unit_type,
            "percentage": round(percentage, 1)
        }

    # Get MT provider breakdown
    mt_breakdown_query = text("""
        SELECT
            provider,
            SUM(amount_usd) as cost_usd,
            SUM(units) as units,
            unit_type
        FROM room_costs
        WHERE ts >= :start_date
          AND ts <= :end_date
          AND pipeline = 'mt'
          AND provider IS NOT NULL
        GROUP BY provider, unit_type
        ORDER BY cost_usd DESC
    """)

    mt_results = db.execute(mt_breakdown_query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()

    mt_breakdown = {}
    for row in mt_results:
        provider = row[0]
        cost = float(row[1])
        units = float(row[2]) if row[2] else 0.0
        unit_type = row[3]
        percentage = (cost / mt_cost * 100) if mt_cost > 0 else 0.0

        mt_breakdown[provider] = {
            "cost_usd": cost,
            "units": units,
            "unit_type": unit_type,
            "percentage": round(percentage, 1)
        }

    return {
        "period": {
            "start": start_date,
            "end": end_date,
            "granularity": granularity
        },
        "totals": {
            "cost_usd": round(total_cost, 2),
            "stt_cost_usd": round(stt_cost, 2),
            "mt_cost_usd": round(mt_cost, 2),
            "total_minutes": round(total_minutes, 2),
            "total_hours": round(total_minutes / 60, 2),
            "active_users": active_users,
            "active_rooms": active_rooms,
            "growth_rate": round(growth_rate, 1) if growth_rate is not None else None
        },
        "stt_breakdown": stt_breakdown,
        "mt_breakdown": mt_breakdown
    }


@router.get("/timeseries")
async def get_cost_timeseries(
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    granularity: str = Query(..., description="hour|day|week|month|year"),
    accumulated: bool = Query(False, description="Return cumulative sum"),
    by_provider: bool = Query(False, description="Break down by provider"),
    user_id: Optional[int] = Query(None, description="Filter by user"),
    room_id: Optional[str] = Query(None, description="Filter by room code"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get time-series cost data for charting.

    Supports different granularities, accumulated view, and per-provider breakdown.
    """

    # Validate granularity
    valid_granularities = ['hour', 'day', 'week', 'month', 'year']
    if granularity not in valid_granularities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid granularity. Must be one of: {', '.join(valid_granularities)}"
        )

    # Build base query with optional filters
    filters = ["rc.ts >= :start_date", "rc.ts <= :end_date"]
    params = {"start_date": start_date, "end_date": end_date}

    if user_id:
        filters.append("r.owner_id = :user_id")
        params["user_id"] = user_id

    if room_id:
        filters.append("rc.room_id = :room_id")
        params["room_id"] = room_id

    where_clause = " AND ".join(filters)

    if by_provider:
        # Per-provider breakdown
        query = text(f"""
            SELECT
                DATE_TRUNC('{granularity}', rc.ts) as timestamp,
                SUM(rc.amount_usd) as total_cost,
                rc.pipeline,
                rc.provider,
                SUM(rc.amount_usd) as cost_usd
            FROM room_costs rc
            {"JOIN rooms r ON rc.room_id = r.code" if user_id else ""}
            WHERE {where_clause}
              AND rc.provider IS NOT NULL
            GROUP BY DATE_TRUNC('{granularity}', rc.ts), rc.pipeline, rc.provider
            ORDER BY timestamp ASC, rc.pipeline, rc.provider
        """)

        results = db.execute(query, params).fetchall()

        # Transform to grouped by timestamp
        data_by_timestamp = {}
        for row in results:
            ts = row[0]
            pipeline = row[2]
            provider = row[3]
            cost = float(row[4])

            if ts not in data_by_timestamp:
                data_by_timestamp[ts] = {
                    "timestamp": ts,
                    "total_cost_usd": 0.0,
                    "providers": {"stt": {}, "mt": {}}
                }

            data_by_timestamp[ts]["total_cost_usd"] += cost
            data_by_timestamp[ts]["providers"][pipeline][provider] = round(cost, 6)

        data_points = sorted(data_by_timestamp.values(), key=lambda x: x["timestamp"])

        # Add accumulated if requested
        if accumulated:
            running_total = 0.0
            for point in data_points:
                running_total += point["total_cost_usd"]
                point["accumulated_cost_usd"] = round(running_total, 2)

    else:
        # Aggregated view (Total, STT, MT)
        query = text(f"""
            SELECT
                DATE_TRUNC('{granularity}', rc.ts) as timestamp,
                SUM(rc.amount_usd) as total_cost_usd,
                SUM(CASE WHEN rc.pipeline = 'stt' THEN rc.amount_usd ELSE 0 END) as stt_cost_usd,
                SUM(CASE WHEN rc.pipeline = 'mt' THEN rc.amount_usd ELSE 0 END) as mt_cost_usd,
                COUNT(*) as event_count
            FROM room_costs rc
            {"JOIN rooms r ON rc.room_id = r.code" if user_id else ""}
            WHERE {where_clause}
            GROUP BY DATE_TRUNC('{granularity}', rc.ts)
            ORDER BY timestamp ASC
        """)

        results = db.execute(query, params).fetchall()

        data_points = []
        running_total = 0.0
        running_stt = 0.0
        running_mt = 0.0

        for row in results:
            total_cost = float(row[1])
            stt_cost = float(row[2])
            mt_cost = float(row[3])

            point = {
                "timestamp": row[0],
                "total_cost_usd": round(total_cost, 2),
                "stt_cost_usd": round(stt_cost, 2),
                "mt_cost_usd": round(mt_cost, 2),
                "event_count": int(row[4])
            }

            if accumulated:
                running_total += total_cost
                running_stt += stt_cost
                running_mt += mt_cost

                point["accumulated_cost_usd"] = round(running_total, 2)
                point["accumulated_stt_cost_usd"] = round(running_stt, 2)
                point["accumulated_mt_cost_usd"] = round(running_mt, 2)

            data_points.append(point)

    return {
        "granularity": granularity,
        "accumulated": accumulated,
        "by_provider": by_provider,
        "data": data_points
    }


@router.get("/users")
async def get_user_costs(
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("total_cost", description="total_cost|stt_cost|mt_cost|room_count"),
    sort_order: str = Query("desc", description="asc|desc"),
    search: Optional[str] = Query(None, description="Search by email or display name"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of users with their cost breakdowns.

    Sorted by cost (highest first by default) with optional search.
    """

    # Validate sort parameters
    valid_sort_fields = {
        "total_cost": "total_cost_usd",
        "stt_cost": "stt_cost_usd",
        "mt_cost": "mt_cost_usd",
        "room_count": "room_count"
    }

    if sort_by not in valid_sort_fields:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by. Must be one of: {', '.join(valid_sort_fields.keys())}")

    if sort_order not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Invalid sort_order. Must be 'asc' or 'desc'")

    sort_field = valid_sort_fields[sort_by]

    # Build search filter
    search_filter = ""
    params = {"start_date": start_date, "end_date": end_date, "limit": limit, "offset": offset}

    if search:
        search_filter = "AND (u.email ILIKE :search OR u.display_name ILIKE :search)"
        params["search"] = f"%{search}%"

    # Get total count
    count_query = text(f"""
        SELECT COUNT(DISTINCT u.id)
        FROM users u
        JOIN rooms r ON r.owner_id = u.id
        JOIN room_costs rc ON rc.room_id = r.code
        WHERE rc.ts >= :start_date AND rc.ts <= :end_date
        {search_filter}
    """)

    total_users = db.execute(count_query, params).scalar() or 0

    # Get user costs with pagination
    users_query = text(f"""
        WITH user_costs AS (
            SELECT
                u.id as user_id,
                u.email,
                u.display_name,
                COUNT(DISTINCT r.id) as room_count,
                SUM(CASE WHEN rc.pipeline = 'stt' THEN rc.amount_usd ELSE 0 END) as stt_cost_usd,
                SUM(CASE WHEN rc.pipeline = 'stt' AND rc.unit_type = 'seconds' THEN rc.units ELSE 0 END) / 60.0 as stt_minutes,
                SUM(CASE WHEN rc.pipeline = 'mt' THEN rc.amount_usd ELSE 0 END) as mt_cost_usd,
                SUM(CASE WHEN rc.pipeline = 'mt' AND rc.unit_type = 'tokens' THEN rc.units ELSE 0 END) as mt_tokens,
                SUM(CASE WHEN rc.pipeline = 'mt' AND rc.unit_type = 'characters' THEN rc.units ELSE 0 END) as mt_characters,
                SUM(rc.amount_usd) as total_cost_usd
            FROM users u
            JOIN rooms r ON r.owner_id = u.id
            JOIN room_costs rc ON rc.room_id = r.code
            WHERE rc.ts >= :start_date AND rc.ts <= :end_date
            {search_filter}
            GROUP BY u.id, u.email, u.display_name
            HAVING SUM(rc.amount_usd) > 0
        ),
        top_stt_providers AS (
            SELECT DISTINCT ON (r.owner_id)
                r.owner_id,
                rc.provider as top_stt_provider
            FROM room_costs rc
            JOIN rooms r ON rc.room_id = r.code
            WHERE rc.pipeline = 'stt'
              AND rc.ts >= :start_date AND rc.ts <= :end_date
              AND rc.provider IS NOT NULL
            GROUP BY r.owner_id, rc.provider
            ORDER BY r.owner_id, SUM(rc.amount_usd) DESC
        ),
        top_mt_providers AS (
            SELECT DISTINCT ON (r.owner_id)
                r.owner_id,
                rc.provider as top_mt_provider
            FROM room_costs rc
            JOIN rooms r ON rc.room_id = r.code
            WHERE rc.pipeline = 'mt'
              AND rc.ts >= :start_date AND rc.ts <= :end_date
              AND rc.provider IS NOT NULL
            GROUP BY r.owner_id, rc.provider
            ORDER BY r.owner_id, SUM(rc.amount_usd) DESC
        )
        SELECT
            uc.*,
            tsp.top_stt_provider,
            tmp.top_mt_provider
        FROM user_costs uc
        LEFT JOIN top_stt_providers tsp ON uc.user_id = tsp.owner_id
        LEFT JOIN top_mt_providers tmp ON uc.user_id = tmp.owner_id
        ORDER BY {sort_field} {sort_order.upper()}
        LIMIT :limit OFFSET :offset
    """)

    users_results = db.execute(users_query, params).fetchall()

    users = []
    for row in users_results:
        users.append({
            "user_id": row[0],
            "email": row[1],
            "display_name": row[2],
            "room_count": row[3],
            "stt_cost_usd": round(float(row[4]), 2),
            "stt_minutes": round(float(row[5]), 2),
            "mt_cost_usd": round(float(row[6]), 2),
            "mt_tokens": round(float(row[7]), 0) if row[7] else None,
            "mt_characters": round(float(row[8]), 0) if row[8] else None,
            "total_cost_usd": round(float(row[9]), 2),
            "top_stt_provider": row[10],
            "top_mt_provider": row[11]
        })

    return {
        "total_users": total_users,
        "page": {
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_users
        },
        "users": users
    }


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: int,
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get detailed cost information for a specific user.

    Includes provider breakdown, rooms, and daily cost trend.
    """

    # Get user info
    user_query = text("""
        SELECT id, email, display_name, created_at
        FROM users
        WHERE id = :user_id
    """)

    user = db.execute(user_query, {"user_id": user_id}).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Get cost summary
    summary_query = text("""
        SELECT
            SUM(rc.amount_usd) as total_cost_usd,
            SUM(CASE WHEN rc.pipeline = 'stt' THEN rc.amount_usd ELSE 0 END) as stt_cost_usd,
            SUM(CASE WHEN rc.pipeline = 'mt' THEN rc.amount_usd ELSE 0 END) as mt_cost_usd,
            COUNT(DISTINCT r.id) as room_count
        FROM rooms r
        JOIN room_costs rc ON rc.room_id = r.code
        WHERE r.owner_id = :user_id
          AND rc.ts >= :start_date AND rc.ts <= :end_date
    """)

    summary = db.execute(summary_query, {
        "user_id": user_id,
        "start_date": start_date,
        "end_date": end_date
    }).fetchone()

    # Get provider usage breakdown
    provider_query = text("""
        SELECT
            rc.pipeline,
            rc.provider,
            SUM(rc.amount_usd) as cost_usd,
            SUM(rc.units) as units,
            rc.unit_type
        FROM rooms r
        JOIN room_costs rc ON rc.room_id = r.code
        WHERE r.owner_id = :user_id
          AND rc.ts >= :start_date AND rc.ts <= :end_date
          AND rc.provider IS NOT NULL
        GROUP BY rc.pipeline, rc.provider, rc.unit_type
        ORDER BY rc.pipeline, cost_usd DESC
    """)

    provider_results = db.execute(provider_query, {
        "user_id": user_id,
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()

    # Calculate total costs by pipeline for percentage
    stt_total = float(summary[1]) if summary and summary[1] else 0.0
    mt_total = float(summary[2]) if summary and summary[2] else 0.0

    provider_usage = {"stt": {}, "mt": {}}
    for row in provider_results:
        pipeline = row[0]
        provider = row[1]
        cost = float(row[2])
        units = float(row[3]) if row[3] else 0.0
        unit_type = row[4]

        total = stt_total if pipeline == 'stt' else mt_total
        percentage = (cost / total * 100) if total > 0 else 0.0

        provider_usage[pipeline][provider] = {
            "percentage": round(percentage, 1),
            "cost_usd": round(cost, 2),
            "units": round(units, 2) if unit_type == 'seconds' else round(units, 0),
            "unit_type": unit_type
        }

        # Convert seconds to minutes for display
        if unit_type == 'seconds':
            provider_usage[pipeline][provider]["minutes"] = round(units / 60, 2)

    # Get user's rooms
    rooms_query = text("""
        SELECT
            r.id,
            r.code,
            r.created_at,
            r.is_public,
            SUM(CASE WHEN rc.pipeline = 'stt' THEN rc.amount_usd ELSE 0 END) as stt_cost_usd,
            SUM(CASE WHEN rc.pipeline = 'mt' THEN rc.amount_usd ELSE 0 END) as mt_cost_usd,
            SUM(rc.amount_usd) as total_cost_usd
        FROM rooms r
        LEFT JOIN room_costs rc ON rc.room_id = r.code
          AND rc.ts >= :start_date AND rc.ts <= :end_date
        WHERE r.owner_id = :user_id
        GROUP BY r.id, r.code, r.created_at, r.is_public
        HAVING SUM(rc.amount_usd) > 0
        ORDER BY total_cost_usd DESC
    """)

    rooms_results = db.execute(rooms_query, {
        "user_id": user_id,
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()

    rooms = []
    for row in rooms_results:
        rooms.append({
            "room_id": row[0],
            "room_code": row[1],
            "created_at": row[2],
            "is_public": row[3],
            "stt_cost_usd": round(float(row[4]), 2),
            "mt_cost_usd": round(float(row[5]), 2),
            "total_cost_usd": round(float(row[6]), 2)
        })

    # Get daily costs
    daily_query = text("""
        SELECT
            DATE(rc.ts) as date,
            SUM(rc.amount_usd) as cost_usd
        FROM rooms r
        JOIN room_costs rc ON rc.room_id = r.code
        WHERE r.owner_id = :user_id
          AND rc.ts >= :start_date AND rc.ts <= :end_date
        GROUP BY DATE(rc.ts)
        ORDER BY date ASC
    """)

    daily_results = db.execute(daily_query, {
        "user_id": user_id,
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()

    daily_costs = [
        {"date": row[0].isoformat(), "cost_usd": round(float(row[1]), 2)}
        for row in daily_results
    ]

    return {
        "user": {
            "user_id": user[0],
            "email": user[1],
            "display_name": user[2],
            "created_at": user[3]
        },
        "summary": {
            "total_cost_usd": round(float(summary[0]), 2) if summary and summary[0] else 0.0,
            "stt_cost_usd": round(stt_total, 2),
            "mt_cost_usd": round(mt_total, 2),
            "room_count": summary[3] if summary else 0
        },
        "provider_usage": provider_usage,
        "rooms": rooms,
        "daily_costs": daily_costs
    }


@router.get("/rooms")
async def get_room_costs(
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    user_id: Optional[int] = Query(None, description="Filter by room owner"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("total_cost", description="total_cost|stt_cost|mt_cost|created_at"),
    sort_order: str = Query("desc", description="asc|desc"),
    search: Optional[str] = Query(None, description="Search by room code"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of rooms with their cost breakdowns.

    Optionally filter by owner, sorted by cost (highest first by default).
    """

    # Validate sort parameters
    valid_sort_fields = {
        "total_cost": "total_cost_usd",
        "stt_cost": "stt_cost_usd",
        "mt_cost": "mt_cost_usd",
        "created_at": "r.created_at"
    }

    if sort_by not in valid_sort_fields:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by. Must be one of: {', '.join(valid_sort_fields.keys())}")

    if sort_order not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Invalid sort_order. Must be 'asc' or 'desc'")

    sort_field = valid_sort_fields[sort_by]

    # Build filters
    filters = ["rc.ts >= :start_date", "rc.ts <= :end_date"]
    params = {"start_date": start_date, "end_date": end_date, "limit": limit, "offset": offset}

    if user_id:
        filters.append("r.owner_id = :user_id")
        params["user_id"] = user_id

    if search:
        filters.append("r.code ILIKE :search")
        params["search"] = f"%{search}%"

    where_clause = " AND ".join(filters)

    # Get total count
    count_query = text(f"""
        SELECT COUNT(DISTINCT r.id)
        FROM rooms r
        JOIN room_costs rc ON rc.room_id = r.code
        WHERE {where_clause}
    """)

    total_rooms = db.execute(count_query, params).scalar() or 0

    # Get rooms with costs
    rooms_query = text(f"""
        SELECT
            r.id,
            r.code,
            r.is_public,
            r.owner_id,
            u.email as owner_email,
            u.display_name as owner_name,
            r.created_at,
            SUM(CASE WHEN rc.pipeline = 'stt' THEN rc.amount_usd ELSE 0 END) as stt_cost_usd,
            SUM(CASE WHEN rc.pipeline = 'stt' AND rc.unit_type = 'seconds' THEN rc.units ELSE 0 END) / 60.0 as stt_minutes,
            SUM(CASE WHEN rc.pipeline = 'mt' THEN rc.amount_usd ELSE 0 END) as mt_cost_usd,
            SUM(rc.amount_usd) as total_cost_usd
        FROM rooms r
        JOIN users u ON r.owner_id = u.id
        JOIN room_costs rc ON rc.room_id = r.code
        WHERE {where_clause}
        GROUP BY r.id, r.code, r.is_public, r.owner_id, u.email, u.display_name, r.created_at
        HAVING SUM(rc.amount_usd) > 0
        ORDER BY {sort_field} {sort_order.upper()}
        LIMIT :limit OFFSET :offset
    """)

    rooms_results = db.execute(rooms_query, params).fetchall()

    rooms = []
    for row in rooms_results:
        rooms.append({
            "room_id": row[0],
            "room_code": row[1],
            "is_public": row[2],
            "owner": {
                "user_id": row[3],
                "email": row[4],
                "display_name": row[5]
            },
            "created_at": row[6],
            "stt_cost_usd": round(float(row[7]), 2),
            "stt_minutes": round(float(row[8]), 2),
            "mt_cost_usd": round(float(row[9]), 2),
            "total_cost_usd": round(float(row[10]), 2)
        })

    return {
        "total_rooms": total_rooms,
        "page": {
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_rooms
        },
        "rooms": rooms
    }
