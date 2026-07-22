from app.models.database import execute_query, execute_single
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

# Month display order: Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec, Jan, Feb, Mar
MONTH_DISPLAY_ORDER = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
MONTH_NAMES = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
}

def _compute_month_status(month_num: int, year: int, rental_start, rental_end) -> str:
    """
    Compute status for a given month/year cell:
    - Not Applicable: month is outside rental period
    - Paid: month is within rental period and in the past
    - Due This Month: month is within rental period and is the current month
    - Upcoming: month is within rental period and in the future
    """
    today = date.today()
    # First day of the target month
    month_start = date(year, month_num, 1)
    # Last day of the target month
    if month_num == 12:
        month_end = date(year + 1, 1, 1).__class__(year, 12, 31)
    else:
        import calendar
        last_day = calendar.monthrange(year, month_num)[1]
        month_end = date(year, month_num, last_day)

    # Parse rental dates
    if isinstance(rental_start, str):
        try:
            rental_start = date.fromisoformat(rental_start)
        except Exception:
            rental_start = None
    if isinstance(rental_end, str):
        try:
            rental_end = date.fromisoformat(rental_end)
        except Exception:
            rental_end = None

    # Check if month overlaps with rental period
    period_start = rental_start if rental_start else date.min
    period_end = rental_end if rental_end else date.max

    # Not within rental period
    if month_end < period_start or month_start > period_end:
        return 'Not Applicable'

    # Current month
    if month_num == today.month and year == today.year:
        return 'Due This Month'

    # Past month within rental period
    if month_start < date(today.year, today.month, 1):
        return 'Paid'

    # Future month within rental period
    return 'Upcoming'


def _build_base_conditions(filters: dict):
    """Build shared WHERE conditions for rental queries."""
    conditions = [
        "d.ownership_type = 'Rented'",
        "d.rental_cost_frequency = 'Monthly'",
        "d.is_deleted = FALSE"
    ]
    params = []

    if filters:
        if filters.get('search'):
            conditions.append("(d.brand LIKE %s OR d.model LIKE %s OR d.vendor_name LIKE %s OR d.serial_number LIKE %s)")
            s = f"%{filters['search']}%"
            params.extend([s, s, s, s])
        if filters.get('vendor'):
            conditions.append("d.vendor_name = %s")
            params.append(filters['vendor'])
        if filters.get('device_type'):
            conditions.append("d.device_type = %s")
            params.append(filters['device_type'])
        if filters.get('status'):
            conditions.append("d.status = %s")
            params.append(filters['status'])
        if filters.get('department'):
            conditions.append("e.department = %s")
            params.append(filters['department'])
        if filters.get('active_only'):
            today_str = date.today().isoformat()
            conditions.append("(d.rental_end_date IS NULL OR d.rental_end_date >= %s)")
            params.append(today_str)
        if filters.get('expiring_soon'):
            from datetime import timedelta
            cutoff = (date.today() + timedelta(days=30)).isoformat()
            today_str = date.today().isoformat()
            conditions.append("d.renewal_date BETWEEN %s AND %s")
            params.extend([today_str, cutoff])

    return conditions, params


def get_rental_matrix(filters: dict = None, page: int = 1, page_size: int = 25, paginate: bool = True):
    """
    Returns paginated rental matrix rows.
    Each row includes a 'months' dict keyed by month name with {amount, status}.
    """
    year = int(filters.get('year', date.today().year)) if filters else date.today().year
    month_filter = filters.get('month') if filters else None

    conditions, params = _build_base_conditions(filters)
    where_clause = "WHERE " + " AND ".join(conditions)

    count_row = execute_single(f"""
        SELECT COUNT(DISTINCT d.id) AS total
        FROM devices d
        LEFT JOIN device_assignments da ON d.id = da.device_id AND da.returned_date IS NULL
        LEFT JOIN employee e ON da.employee_name = e.name
        {where_clause}
    """, tuple(params) if params else None)
    total_count = count_row['total'] if count_row else 0

    offset = (page - 1) * page_size
    query_params = list(params)

    if paginate:
        query_params.extend([page_size, offset])
        limit_clause = "LIMIT %s OFFSET %s"
    else:
        limit_clause = ""

    rows = execute_query(f"""
        SELECT d.id, d.brand, d.model, d.serial_number, d.asset_id, d.device_type,
               d.vendor_name, d.vendor_contact,
               d.rental_start_date, d.rental_end_date, d.renewal_date,
               d.rental_cost, d.rental_cost_frequency, d.status,
               da.employee_name AS assigned_to, e.department AS employee_department
        FROM devices d
        LEFT JOIN device_assignments da ON d.id = da.device_id AND da.returned_date IS NULL
        LEFT JOIN employee e ON da.employee_name = e.name
        {where_clause}
        ORDER BY d.brand ASC, d.model ASC
        {limit_clause}
    """, tuple(query_params) if query_params else None)

    result = []
    for r in rows:
        # Serialize date fields
        for k in ('rental_start_date', 'rental_end_date', 'renewal_date'):
            if r.get(k) and hasattr(r[k], 'isoformat'):
                r[k] = r[k].isoformat()

        monthly_rate = float(r.get('rental_cost') or 0)
        rental_start = r.get('rental_start_date')
        rental_end = r.get('rental_end_date')

        months = {}
        for m in MONTH_DISPLAY_ORDER:
            status = _compute_month_status(m, year, rental_start, rental_end)
            months[MONTH_NAMES[m]] = {
                'amount': monthly_rate if status != 'Not Applicable' else 0,
                'status': status
            }

        # Apply month filter - skip rows that don't have the filtered month active
        if month_filter and month_filter in months:
            if months[month_filter]['status'] == 'Not Applicable':
                continue

        r['months'] = months
        # Compute current month status for Status column
        r['current_status_label'] = months.get(MONTH_NAMES[date.today().month], {}).get('status', 'Not Applicable')
        result.append(r)

    return {
        'rows': result,
        'total_count': total_count,
        'page': page,
        'page_size': page_size,
        'total_pages': max(1, -(-total_count // page_size)) if paginate else 1
    }


def get_vendor_summary(filters: dict = None):
    """Returns vendor aggregations for the left-rail summary panel."""
    conditions, params = _build_base_conditions(filters)
    where_clause = "WHERE " + " AND ".join(conditions)

    rows = execute_query(f"""
        SELECT d.vendor_name,
               COUNT(DISTINCT d.id) AS asset_count,
               SUM(d.rental_cost) AS total_monthly_amount
        FROM devices d
        LEFT JOIN device_assignments da ON d.id = da.device_id AND da.returned_date IS NULL
        LEFT JOIN employee e ON da.employee_name = e.name
        {where_clause}
        GROUP BY d.vendor_name
        ORDER BY total_monthly_amount DESC
    """, tuple(params) if params else None)

    for r in rows:
        r['total_monthly_amount'] = float(r.get('total_monthly_amount') or 0)

    return rows


def get_month_summary(filters: dict = None):
    """Returns per-month cost and active asset count for the horizontal strip."""
    year = int(filters.get('year', date.today().year)) if filters else date.today().year
    conditions, params = _build_base_conditions(filters)
    where_clause = "WHERE " + " AND ".join(conditions)

    rows = execute_query(f"""
        SELECT d.id, d.rental_cost, d.rental_start_date, d.rental_end_date
        FROM devices d
        LEFT JOIN device_assignments da ON d.id = da.device_id AND da.returned_date IS NULL
        LEFT JOIN employee e ON da.employee_name = e.name
        {where_clause}
    """, tuple(params) if params else None)

    month_data = {MONTH_NAMES[m]: {'total_cost': 0.0, 'asset_count': 0, 'month_num': m} for m in MONTH_DISPLAY_ORDER}

    for r in rows:
        cost = float(r.get('rental_cost') or 0)
        for m in MONTH_DISPLAY_ORDER:
            status = _compute_month_status(m, year, r.get('rental_start_date'), r.get('rental_end_date'))
            if status != 'Not Applicable':
                month_data[MONTH_NAMES[m]]['total_cost'] += cost
                month_data[MONTH_NAMES[m]]['asset_count'] += 1

    # Return as ordered list
    return [{'month': MONTH_NAMES[m], **month_data[MONTH_NAMES[m]]} for m in MONTH_DISPLAY_ORDER]


def get_rental_dashboard_stats(filters: dict = None):
    """Returns the 4 summary card stats."""
    from datetime import timedelta
    conditions, params = _build_base_conditions(filters)
    where_clause = "WHERE " + " AND ".join(conditions)

    today_str = date.today().isoformat()
    cutoff_str = (date.today() + timedelta(days=30)).isoformat()

    # Total assets count & monthly cost (active rentals)
    summary = execute_single(f"""
        SELECT COUNT(DISTINCT d.id) AS total_rental_assets,
               SUM(CASE WHEN (d.rental_end_date IS NULL OR d.rental_end_date >= %s) THEN d.rental_cost ELSE 0 END) AS total_monthly_cost,
               COUNT(DISTINCT d.vendor_name) AS active_vendors
        FROM devices d
        LEFT JOIN device_assignments da ON d.id = da.device_id AND da.returned_date IS NULL
        LEFT JOIN employee e ON da.employee_name = e.name
        {where_clause}
    """, tuple([today_str] + params))

    # Upcoming renewals
    renewals = execute_single(f"""
        SELECT COUNT(*) AS upcoming_renewals
        FROM devices d
        LEFT JOIN device_assignments da ON d.id = da.device_id AND da.returned_date IS NULL
        LEFT JOIN employee e ON da.employee_name = e.name
        {where_clause}
        AND d.renewal_date BETWEEN %s AND %s
    """, tuple(params + [today_str, cutoff_str]))

    return {
        'total_rental_assets': summary.get('total_rental_assets', 0) if summary else 0,
        'total_monthly_cost': float(summary.get('total_monthly_cost') or 0) if summary else 0,
        'active_vendors': summary.get('active_vendors', 0) if summary else 0,
        'upcoming_renewals': renewals.get('upcoming_renewals', 0) if renewals else 0
    }
