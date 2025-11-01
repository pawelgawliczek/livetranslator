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
    room_id: Optional[str] = Query(None, description="Filter by room code"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get cost overview with provider breakdown.

    Can filter by room_id and/or user_id to get context-specific analytics.
    Returns total costs, STT/MT breakdown, usage metrics, and provider details.
    """

    # Auto-detect granularity if not provided
    if not granularity:
        granularity = auto_detect_granularity(start_date, end_date)

    # Build WHERE clause with optional filters
    where_conditions = ["ts >= :start_date", "ts <= :end_date"]
    query_params = {
        "start_date": start_date,
        "end_date": end_date
    }

    if room_id:
        where_conditions.append("room_id = :room_id")
        query_params["room_id"] = room_id

    if user_id:
        where_conditions.append("""
            room_id IN (
                SELECT code FROM rooms WHERE owner_id = :user_id
            )
        """)
        query_params["user_id"] = user_id

    where_clause = " AND ".join(where_conditions)

    # Get total costs
    totals_query = text(f"""
        SELECT
            COALESCE(SUM(amount_usd), 0) as total_cost,
            COALESCE(SUM(CASE WHEN pipeline = 'stt' THEN amount_usd ELSE 0 END), 0) as stt_cost,
            COALESCE(SUM(CASE WHEN pipeline = 'mt' THEN amount_usd ELSE 0 END), 0) as mt_cost,
            COALESCE(SUM(CASE WHEN pipeline = 'stt' AND unit_type = 'seconds' THEN units ELSE 0 END), 0) / 60.0 as total_minutes,
            COUNT(DISTINCT room_id) as active_rooms
        FROM room_costs
        WHERE {where_clause}
    """)

    totals = db.execute(totals_query, query_params).fetchone()

    total_cost = float(totals[0])
    stt_cost = float(totals[1])
    mt_cost = float(totals[2])
    total_minutes = float(totals[3])
    active_rooms = int(totals[4])

    # Get active users count (users who created rooms with activity)
    users_where_conditions = ["rc.ts >= :start_date", "rc.ts <= :end_date"]
    if room_id:
        users_where_conditions.append("rc.room_id = :room_id")
    if user_id:
        users_where_conditions.append("r.owner_id = :user_id")

    users_where_clause = " AND ".join(users_where_conditions)

    users_query = text(f"""
        SELECT COUNT(DISTINCT r.owner_id)
        FROM room_costs rc
        JOIN rooms r ON rc.room_id = r.code
        WHERE {users_where_clause}
    """)

    active_users = db.execute(users_query, query_params).scalar() or 0

    # Calculate growth rate
    growth_rate = calculate_growth_rate(db, start_date, end_date, total_cost)

    # Get STT provider breakdown
    stt_where_conditions = where_conditions.copy()
    stt_where_conditions.append("pipeline = 'stt'")
    stt_where_conditions.append("provider IS NOT NULL")
    stt_where_clause = " AND ".join(stt_where_conditions)

    stt_breakdown_query = text(f"""
        SELECT
            provider,
            SUM(amount_usd) as cost_usd,
            SUM(units) as units,
            unit_type
        FROM room_costs
        WHERE {stt_where_clause}
        GROUP BY provider, unit_type
        ORDER BY cost_usd DESC
    """)

    stt_results = db.execute(stt_breakdown_query, query_params).fetchall()

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
    mt_where_conditions = where_conditions.copy()
    mt_where_conditions.append("pipeline = 'mt'")
    mt_where_conditions.append("provider IS NOT NULL")
    mt_where_clause = " AND ".join(mt_where_conditions)

    mt_breakdown_query = text(f"""
        SELECT
            provider,
            SUM(amount_usd) as cost_usd,
            SUM(units) as units,
            unit_type
        FROM room_costs
        WHERE {mt_where_clause}
        GROUP BY provider, unit_type
        ORDER BY cost_usd DESC
    """)

    mt_results = db.execute(mt_breakdown_query, query_params).fetchall()

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

    # Get rooms with costs (including multi-speaker info)
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
            SUM(rc.amount_usd) as total_cost_usd,
            r.speakers_locked,
            (SELECT COUNT(*) FROM room_speakers WHERE room_id = r.id) as speaker_count
        FROM rooms r
        JOIN users u ON r.owner_id = u.id
        JOIN room_costs rc ON rc.room_id = r.code
        WHERE {where_clause}
        GROUP BY r.id, r.code, r.is_public, r.owner_id, u.email, u.display_name, r.created_at, r.speakers_locked
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
            "total_cost_usd": round(float(row[10]), 2),
            "is_multi_speaker": row[11],  # speakers_locked
            "speaker_count": row[12] if row[12] else 0
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


# ============================================================================
# Multi-Speaker Room Analytics (Phase 3.3)
# ============================================================================

@router.get("/multi-speaker/overview")
async def get_multi_speaker_overview(
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get aggregate multi-speaker statistics for admin dashboard.

    Returns:
        - Active multi-speaker room count
        - Total multi-speaker cost
        - Average speakers per room
        - Highest cost room
        - Multi-speaker cost trend
    """

    # Get multi-speaker room count and stats
    ms_query = text("""
        WITH multi_speaker_rooms AS (
            SELECT DISTINCT r.id, r.code, r.created_at
            FROM rooms r
            WHERE r.speakers_locked = TRUE
              AND r.created_at >= :start_date
              AND r.created_at <= :end_date
        ),
        room_costs AS (
            SELECT
                r.id as room_id,
                r.code as room_code,
                COUNT(DISTINCT rs.speaker_id) as speaker_count,
                SUM(rc.amount_usd) as total_cost,
                SUM(CASE WHEN rc.pipeline = 'mt' THEN rc.amount_usd ELSE 0 END) as mt_cost
            FROM multi_speaker_rooms r
            LEFT JOIN room_speakers rs ON rs.room_id = r.id
            LEFT JOIN room_costs rc ON rc.room_id = r.code
              AND rc.ts >= :start_date AND rc.ts <= :end_date
            GROUP BY r.id, r.code
        )
        SELECT
            COUNT(*) as total_multi_speaker_rooms,
            COALESCE(SUM(total_cost), 0) as total_ms_cost,
            COALESCE(AVG(speaker_count), 0) as avg_speakers_per_room,
            COUNT(*) FILTER (WHERE total_cost > 1.0) as high_cost_room_count
        FROM room_costs
    """)

    result = db.execute(ms_query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchone()

    # Get total rooms for percentage calculation
    total_rooms_query = text("""
        SELECT COUNT(*)
        FROM rooms
        WHERE created_at >= :start_date AND created_at <= :end_date
    """)

    total_rooms = db.execute(total_rooms_query, {
        "start_date": start_date,
        "end_date": end_date
    }).scalar() or 0

    # Get highest cost room
    highest_cost_query = text("""
        WITH multi_speaker_rooms AS (
            SELECT r.id, r.code, r.created_at
            FROM rooms r
            WHERE r.speakers_locked = TRUE
              AND r.created_at >= :start_date
              AND r.created_at <= :end_date
        )
        SELECT
            r.code as room_code,
            r.id as room_id,
            COUNT(DISTINCT rs.speaker_id) as speaker_count,
            SUM(rc.amount_usd) as total_cost
        FROM multi_speaker_rooms r
        LEFT JOIN room_speakers rs ON rs.room_id = r.id
        LEFT JOIN room_costs rc ON rc.room_id = r.code
          AND rc.ts >= :start_date AND rc.ts <= :end_date
        GROUP BY r.id, r.code
        HAVING SUM(rc.amount_usd) > 0
        ORDER BY total_cost DESC
        LIMIT 1
    """)

    highest_cost_room = db.execute(highest_cost_query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchone()

    ms_rooms = result[0] if result else 0
    ms_cost = float(result[1]) if result and result[1] else 0.0
    avg_speakers = float(result[2]) if result and result[2] else 0.0
    high_cost_count = result[3] if result else 0

    ms_percentage = (ms_rooms / total_rooms * 100) if total_rooms > 0 else 0.0

    return {
        "active_multi_speaker_rooms": ms_rooms,
        "total_rooms": total_rooms,
        "multi_speaker_percentage": round(ms_percentage, 1),
        "total_multi_speaker_cost_usd": round(ms_cost, 2),
        "average_speakers_per_room": round(avg_speakers, 1),
        "high_cost_room_count": high_cost_count,
        "highest_cost_room": {
            "room_code": highest_cost_room[0] if highest_cost_room else None,
            "room_id": highest_cost_room[1] if highest_cost_room else None,
            "speaker_count": highest_cost_room[2] if highest_cost_room else 0,
            "total_cost_usd": round(float(highest_cost_room[3]), 2) if highest_cost_room else 0.0
        } if highest_cost_room else None
    }


@router.get("/rooms/{room_code}/multi-speaker-details")
async def get_room_multi_speaker_details(
    room_code: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive multi-speaker analytics for a specific room.

    Returns:
        - Room info (owner, created, status, duration)
        - Speaker configuration (names, languages, colors)
        - Translation matrix (N × N-1)
        - Cost breakdown (STT, MT, total, session, projections)
    """

    # Get room info
    room_query = text("""
        SELECT
            r.id,
            r.code,
            r.created_at,
            r.speakers_locked,
            r.owner_id,
            u.email as owner_email,
            u.display_name as owner_name
        FROM rooms r
        JOIN users u ON r.owner_id = u.id
        WHERE r.code = :room_code
    """)

    room = db.execute(room_query, {"room_code": room_code}).fetchone()

    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_code} not found")

    if not room[3]:  # speakers_locked
        raise HTTPException(
            status_code=400,
            detail=f"Room {room_code} is not a multi-speaker room"
        )

    room_id = room[0]

    # Get speakers
    speakers_query = text("""
        SELECT
            speaker_id,
            display_name,
            language,
            color,
            created_at
        FROM room_speakers
        WHERE room_id = :room_id
        ORDER BY speaker_id
    """)

    speakers = db.execute(speakers_query, {"room_id": room_id}).fetchall()

    num_speakers = len(speakers)
    translation_matrix_count = num_speakers * (num_speakers - 1) if num_speakers > 1 else 0

    # Get costs
    costs_query = text("""
        SELECT
            SUM(CASE WHEN pipeline = 'stt' THEN amount_usd ELSE 0 END) as stt_cost,
            SUM(CASE WHEN pipeline = 'mt' THEN amount_usd ELSE 0 END) as mt_cost,
            SUM(amount_usd) as total_cost,
            MIN(ts) as first_event,
            MAX(ts) as last_event,
            COUNT(DISTINCT CASE WHEN pipeline = 'stt' THEN segment_id END) as total_segments,
            SUM(CASE WHEN pipeline = 'stt' AND unit_type = 'seconds' THEN units ELSE 0 END) / 60.0 as total_minutes
        FROM room_costs
        WHERE room_id = :room_code
    """)

    costs = db.execute(costs_query, {"room_code": room_code}).fetchone()

    stt_cost = float(costs[0]) if costs and costs[0] else 0.0
    mt_cost = float(costs[1]) if costs and costs[1] else 0.0
    total_cost = float(costs[2]) if costs and costs[2] else 0.0
    first_event = costs[3] if costs else None
    last_event = costs[4] if costs else None
    total_segments = costs[5] if costs else 0
    total_minutes = float(costs[6]) if costs and costs[6] else 0.0

    # Calculate session duration
    session_duration_seconds = 0
    if first_event and last_event:
        session_duration_seconds = (last_event - first_event).total_seconds()

    session_duration_hours = session_duration_seconds / 3600.0 if session_duration_seconds > 0 else 0.0

    # Calculate hourly rates
    stt_per_hour = stt_cost / session_duration_hours if session_duration_hours > 0 else 0.0
    mt_per_hour = mt_cost / session_duration_hours if session_duration_hours > 0 else 0.0
    total_per_hour = total_cost / session_duration_hours if session_duration_hours > 0 else 0.0

    # Calculate projections (8-hour day, 22-day month)
    daily_projection = total_per_hour * 8
    monthly_projection = daily_projection * 22

    return {
        "room": {
            "room_id": room_id,
            "room_code": room[1],
            "created_at": room[2],
            "owner": {
                "user_id": room[4],
                "email": room[5],
                "display_name": room[6]
            },
            "status": "active" if session_duration_seconds > 0 else "inactive",
            "session_duration_seconds": round(session_duration_seconds, 0),
            "session_duration_hours": round(session_duration_hours, 2)
        },
        "speakers": [
            {
                "speaker_id": spk[0],
                "display_name": spk[1],
                "language": spk[2],
                "color": spk[3],
                "enrolled_at": spk[4]
            }
            for spk in speakers
        ],
        "translation_matrix": {
            "num_speakers": num_speakers,
            "translations_per_message": translation_matrix_count,
            "formula": f"{num_speakers} × {num_speakers - 1}" if num_speakers > 1 else "N/A"
        },
        "costs": {
            "stt_cost_usd": round(stt_cost, 2),
            "mt_cost_usd": round(mt_cost, 2),
            "total_cost_usd": round(total_cost, 2),
            "session": {
                "total_segments": total_segments,
                "total_minutes": round(total_minutes, 2),
                "stt_cost_usd": round(stt_cost, 2),
                "mt_cost_usd": round(mt_cost, 2),
                "total_cost_usd": round(total_cost, 2)
            },
            "hourly_rate": {
                "stt_per_hour": round(stt_per_hour, 2),
                "mt_per_hour": round(mt_per_hour, 2),
                "total_per_hour": round(total_per_hour, 2)
            },
            "projections": {
                "daily_8hrs": round(daily_projection, 2),
                "monthly_22days": round(monthly_projection, 2)
            }
        }
    }


@router.get("/rooms/{room_code}/translation-pairs")
async def get_translation_pairs(
    room_code: str,
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get translation pair analysis for multi-speaker room.

    Returns most active translation pairs by volume and cost.
    """

    # Verify room exists and is multi-speaker
    room_query = text("""
        SELECT id, speakers_locked
        FROM rooms
        WHERE code = :room_code
    """)

    room = db.execute(room_query, {"room_code": room_code}).fetchone()

    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_code} not found")

    if not room[1]:  # speakers_locked
        raise HTTPException(
            status_code=400,
            detail=f"Room {room_code} is not a multi-speaker room"
        )

    # Get speaker info for display
    speakers_query = text("""
        SELECT speaker_id, display_name, language
        FROM room_speakers
        WHERE room_id = :room_id
    """)

    speakers = db.execute(speakers_query, {"room_id": room[0]}).fetchall()
    speaker_map = {spk[0]: {"display_name": spk[1], "language": spk[2]} for spk in speakers}

    # Get translation pairs
    pairs_query = text("""
        SELECT
            speaker_id,
            target_speaker_id,
            COUNT(*) as translation_count,
            SUM(amount_usd) as cost_usd
        FROM room_costs
        WHERE room_id = :room_code
          AND speaker_id IS NOT NULL
          AND target_speaker_id IS NOT NULL
          AND pipeline = 'mt'
        GROUP BY speaker_id, target_speaker_id
        ORDER BY translation_count DESC
        LIMIT :limit
    """)

    pairs = db.execute(pairs_query, {
        "room_code": room_code,
        "limit": limit
    }).fetchall()

    # Build response with speaker names
    translation_pairs = []
    for pair in pairs:
        src_speaker_id = pair[0]
        tgt_speaker_id = pair[1]

        src_speaker = speaker_map.get(src_speaker_id, {"display_name": f"Speaker {src_speaker_id}", "language": "unknown"})
        tgt_speaker = speaker_map.get(tgt_speaker_id, {"display_name": f"Speaker {tgt_speaker_id}", "language": "unknown"})

        translation_pairs.append({
            "source_speaker_id": src_speaker_id,
            "source_speaker_name": src_speaker["display_name"],
            "source_language": src_speaker["language"],
            "target_speaker_id": tgt_speaker_id,
            "target_speaker_name": tgt_speaker["display_name"],
            "target_language": tgt_speaker["language"],
            "translation_count": pair[2],
            "cost_usd": round(float(pair[3]), 2)
        })

    return {
        "room_code": room_code,
        "total_pairs": len(translation_pairs),
        "translation_pairs": translation_pairs
    }


@router.get("/rooms/{room_code}/speaker-activity")
async def get_speaker_activity(
    room_code: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get per-speaker activity statistics (airtime, message count, costs).

    Returns speaker usage breakdown for optimization suggestions.
    """

    # Verify room exists and is multi-speaker
    room_query = text("""
        SELECT id, speakers_locked
        FROM rooms
        WHERE code = :room_code
    """)

    room = db.execute(room_query, {"room_code": room_code}).fetchone()

    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_code} not found")

    if not room[1]:  # speakers_locked
        raise HTTPException(
            status_code=400,
            detail=f"Room {room_code} is not a multi-speaker room"
        )

    # Get speaker activity
    activity_query = text("""
        WITH speaker_segments AS (
            SELECT
                speaker_id,
                COUNT(DISTINCT segment_id) as segment_count,
                SUM(CASE WHEN unit_type = 'seconds' THEN units ELSE 0 END) as airtime_seconds
            FROM room_costs
            WHERE room_id = :room_code
              AND speaker_id IS NOT NULL
              AND pipeline = 'stt'
            GROUP BY speaker_id
        ),
        speaker_costs AS (
            SELECT
                speaker_id,
                SUM(amount_usd) as total_cost
            FROM room_costs
            WHERE room_id = :room_code
              AND speaker_id IS NOT NULL
              AND pipeline = 'mt'
            GROUP BY speaker_id
        ),
        total_airtime AS (
            SELECT SUM(airtime_seconds) as total_seconds
            FROM speaker_segments
        )
        SELECT
            rs.speaker_id,
            rs.display_name,
            rs.language,
            rs.color,
            COALESCE(ss.segment_count, 0) as segment_count,
            COALESCE(ss.airtime_seconds, 0) as airtime_seconds,
            COALESCE(sc.total_cost, 0) as mt_cost_usd,
            CASE
                WHEN ta.total_seconds > 0 THEN (COALESCE(ss.airtime_seconds, 0) / ta.total_seconds * 100)
                ELSE 0
            END as airtime_percentage
        FROM room_speakers rs
        LEFT JOIN speaker_segments ss ON ss.speaker_id = rs.speaker_id
        LEFT JOIN speaker_costs sc ON sc.speaker_id = rs.speaker_id
        CROSS JOIN total_airtime ta
        WHERE rs.room_id = :room_id
        ORDER BY airtime_percentage DESC
    """)

    activity = db.execute(activity_query, {
        "room_code": room_code,
        "room_id": room[0]
    }).fetchall()

    speakers = []
    for row in activity:
        speakers.append({
            "speaker_id": row[0],
            "display_name": row[1],
            "language": row[2],
            "color": row[3],
            "segment_count": row[4],
            "airtime_seconds": round(float(row[5]), 0),
            "airtime_minutes": round(float(row[5]) / 60, 2),
            "mt_cost_usd": round(float(row[6]), 2),
            "airtime_percentage": round(float(row[7]), 1)
        })

    return {
        "room_code": room_code,
        "speakers": speakers,
        "total_speakers": len(speakers)
    }


@router.get("/rooms/{room_code}/cost-timeline")
async def get_cost_timeline(
    room_code: str,
    granularity: str = Query("hour", description="hour|day|week"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get cost timeline for a multi-speaker room.

    Returns time-series cost data for charting.
    """

    # Validate granularity
    valid_granularities = ['hour', 'day', 'week']
    if granularity not in valid_granularities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid granularity. Must be one of: {', '.join(valid_granularities)}"
        )

    # Verify room exists
    room_query = text("""
        SELECT id FROM rooms WHERE code = :room_code
    """)

    room = db.execute(room_query, {"room_code": room_code}).fetchone()

    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_code} not found")

    # Get timeline data
    timeline_query = text(f"""
        SELECT
            DATE_TRUNC('{granularity}', ts) as timestamp,
            SUM(amount_usd) as total_cost,
            SUM(CASE WHEN pipeline = 'stt' THEN amount_usd ELSE 0 END) as stt_cost,
            SUM(CASE WHEN pipeline = 'mt' THEN amount_usd ELSE 0 END) as mt_cost,
            COUNT(*) as event_count
        FROM room_costs
        WHERE room_id = :room_code
        GROUP BY DATE_TRUNC('{granularity}', ts)
        ORDER BY timestamp ASC
    """)

    timeline = db.execute(timeline_query, {"room_code": room_code}).fetchall()

    data_points = []
    for row in timeline:
        data_points.append({
            "timestamp": row[0],
            "total_cost_usd": round(float(row[1]), 2),
            "stt_cost_usd": round(float(row[2]), 2),
            "mt_cost_usd": round(float(row[3]), 2),
            "event_count": row[4]
        })

    return {
        "room_code": room_code,
        "granularity": granularity,
        "data": data_points
    }


@router.get("/rooms/{room_code}/optimization-suggestions")
async def get_optimization_suggestions(
    room_code: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get AI-powered cost optimization suggestions for a multi-speaker room.

    Analyzes speaker activity and provides actionable recommendations.
    """

    # Get speaker activity data (reuse existing endpoint logic)
    room_query = text("""
        SELECT id, speakers_locked
        FROM rooms
        WHERE code = :room_code
    """)

    room = db.execute(room_query, {"room_code": room_code}).fetchone()

    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_code} not found")

    if not room[1]:  # speakers_locked
        return {
            "room_code": room_code,
            "suggestions": []
        }

    # Get speaker activity
    activity_query = text("""
        WITH speaker_segments AS (
            SELECT
                speaker_id,
                COUNT(DISTINCT segment_id) as segment_count,
                SUM(CASE WHEN unit_type = 'seconds' THEN units ELSE 0 END) as airtime_seconds
            FROM room_costs
            WHERE room_id = :room_code
              AND speaker_id IS NOT NULL
              AND pipeline = 'stt'
            GROUP BY speaker_id
        ),
        speaker_costs AS (
            SELECT
                speaker_id,
                SUM(amount_usd) as mt_cost
            FROM room_costs
            WHERE room_id = :room_code
              AND speaker_id IS NOT NULL
              AND pipeline = 'mt'
            GROUP BY speaker_id
        ),
        total_airtime AS (
            SELECT SUM(airtime_seconds) as total_seconds
            FROM speaker_segments
        )
        SELECT
            rs.speaker_id,
            rs.display_name,
            rs.language,
            COALESCE(ss.airtime_seconds, 0) as airtime_seconds,
            COALESCE(sc.mt_cost, 0) as mt_cost,
            CASE
                WHEN ta.total_seconds > 0 THEN (COALESCE(ss.airtime_seconds, 0) / ta.total_seconds * 100)
                ELSE 0
            END as airtime_percentage
        FROM room_speakers rs
        LEFT JOIN speaker_segments ss ON ss.speaker_id = rs.speaker_id
        LEFT JOIN speaker_costs sc ON sc.speaker_id = rs.speaker_id
        CROSS JOIN total_airtime ta
        WHERE rs.room_id = :room_id
        ORDER BY airtime_percentage ASC
    """)

    activity = db.execute(activity_query, {
        "room_code": room_code,
        "room_id": room[0]
    }).fetchall()

    suggestions = []

    # Find inactive speakers (less than 10% airtime)
    inactive_speakers = [
        spk for spk in activity
        if float(spk[5]) < 10.0 and float(spk[3]) > 0
    ]

    if inactive_speakers:
        total_savings = sum(float(spk[4]) for spk in inactive_speakers)
        speaker_names = ", ".join(spk[1] for spk in inactive_speakers)

        suggestions.append({
            "type": "inactive_speakers",
            "severity": "medium",
            "title": f"{len(inactive_speakers)} speaker(s) with low activity detected",
            "description": f"{speaker_names} have less than 10% airtime. Consider removing inactive speakers to reduce translation costs.",
            "potential_savings_usd": round(total_savings, 2),
            "affected_speakers": [
                {
                    "speaker_id": spk[0],
                    "display_name": spk[1],
                    "airtime_percentage": round(float(spk[5]), 1)
                }
                for spk in inactive_speakers
            ]
        })

    # Check for language consolidation opportunities
    languages = {}
    for spk in activity:
        lang = spk[2]
        if lang not in languages:
            languages[lang] = []
        languages[lang].append(spk[1])

    if len(languages) > 1:
        primary_lang = max(languages.items(), key=lambda x: len(x[1]))
        if len(primary_lang[1]) >= len(activity) * 0.6:  # 60% or more use same language
            suggestions.append({
                "type": "language_consolidation",
                "severity": "low",
                "title": f"Most speakers use {primary_lang[0]}",
                "description": f"{len(primary_lang[1])} of {len(activity)} speakers use {primary_lang[0]}. If all speakers could communicate in {primary_lang[0]}, translation costs would be eliminated.",
                "potential_savings_usd": round(sum(float(spk[4]) for spk in activity), 2),
                "primary_language": primary_lang[0],
                "speaker_count": len(primary_lang[1])
            })

    return {
        "room_code": room_code,
        "total_suggestions": len(suggestions),
        "suggestions": suggestions
    }
