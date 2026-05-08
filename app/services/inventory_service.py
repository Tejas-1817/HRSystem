"""
Inventory Service
─────────────────
Centralized inventory dashboard, stock queries, catalog CRUD,
asset lifecycle tracking, and stock reconciliation.

Stock counts are ALWAYS computed from the devices table —
never stored as mutable counters.
"""

import logging
from app.models.database import execute_query, execute_single, Transaction

logger = logging.getLogger(__name__)

# Valid device categories
VALID_CATEGORIES = [
    "Laptop", "Monitor", "Keyboard", "Mouse", "Mobile Device",
    "Headphones", "Tablet", "Docking Station", "Other",
]


# ─────────────────────────────────────────────────────────────────────────────
# Inventory Dashboard
# ─────────────────────────────────────────────────────────────────────────────

def get_inventory_dashboard() -> dict:
    """
    Aggregated inventory dashboard with stock counts by status, category,
    and brand — all computed in real time from the devices table.
    """
    # Overall totals
    totals = execute_single("""
        SELECT
            COUNT(*) AS total,
            SUM(status = 'Available')    AS available,
            SUM(status = 'Assigned')     AS assigned,
            SUM(status = 'Under Repair') AS under_repair,
            SUM(status = 'Retired')      AS retired
        FROM devices WHERE is_deleted = FALSE
    """)

    # By category
    by_category = execute_query("""
        SELECT device_type AS category,
            COUNT(*) AS total,
            SUM(status = 'Available')    AS available,
            SUM(status = 'Assigned')     AS assigned,
            SUM(status = 'Under Repair') AS under_repair,
            SUM(status = 'Retired')      AS retired
        FROM devices WHERE is_deleted = FALSE
        GROUP BY device_type ORDER BY device_type
    """)

    # By brand
    by_brand = execute_query("""
        SELECT brand,
            COUNT(*) AS total,
            SUM(status = 'Available')    AS available,
            SUM(status = 'Assigned')     AS assigned,
            SUM(status = 'Under Repair') AS under_repair
        FROM devices WHERE is_deleted = FALSE
        GROUP BY brand ORDER BY brand
    """)

    # Low stock alerts
    alerts = get_low_stock_alerts()

    # Ensure int conversion (MySQL returns Decimal for SUM)
    for d in [totals] + by_category + by_brand:
        for k, v in d.items():
            if isinstance(v, (type(None),)):
                d[k] = 0
            elif hasattr(v, '__int__') and k != 'category' and k != 'brand' and k != 'device_type':
                d[k] = int(v)

    return {
        "totals": totals,
        "by_category": by_category,
        "by_brand": by_brand,
        "low_stock_alerts": alerts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Stock by Catalog SKU
# ─────────────────────────────────────────────────────────────────────────────

def get_stock_by_catalog(catalog_id: int) -> dict:
    """Stock counts for a specific catalog SKU."""
    catalog = execute_single("SELECT * FROM asset_catalog WHERE id = %s", (catalog_id,))
    if not catalog:
        return None

    counts = execute_single("""
        SELECT
            COUNT(*) AS total,
            SUM(status = 'Available')    AS available,
            SUM(status = 'Assigned')     AS assigned,
            SUM(status = 'Under Repair') AS under_repair,
            SUM(status = 'Retired')      AS retired
        FROM devices
        WHERE catalog_id = %s AND is_deleted = FALSE
    """, (catalog_id,))

    for k, v in counts.items():
        counts[k] = int(v) if v else 0

    for k, v in catalog.items():
        if hasattr(v, "isoformat"):
            catalog[k] = v.isoformat()

    return {**catalog, "stock": counts}


# ─────────────────────────────────────────────────────────────────────────────
# Low Stock Alerts
# ─────────────────────────────────────────────────────────────────────────────

def get_low_stock_alerts() -> list[dict]:
    """
    Return catalog entries where available stock < low_stock_threshold.
    """
    rows = execute_query("""
        SELECT ac.id AS catalog_id, ac.category, ac.brand, ac.model,
               ac.low_stock_threshold,
               COUNT(d.id) AS total_units,
               SUM(d.status = 'Available') AS available
        FROM asset_catalog ac
        LEFT JOIN devices d ON d.catalog_id = ac.id AND d.is_deleted = FALSE
        GROUP BY ac.id
        HAVING available < ac.low_stock_threshold
        ORDER BY available ASC
    """)
    for r in rows:
        for k, v in r.items():
            if isinstance(v, type(None)):
                r[k] = 0
            elif hasattr(v, '__int__') and k not in ('category', 'brand', 'model'):
                r[k] = int(v)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Catalog CRUD
# ─────────────────────────────────────────────────────────────────────────────

def list_catalog() -> list[dict]:
    """List all catalog SKUs with real-time stock counts."""
    rows = execute_query("""
        SELECT ac.*,
               COUNT(d.id) AS total_units,
               COALESCE(SUM(d.status = 'Available'), 0)    AS available,
               COALESCE(SUM(d.status = 'Assigned'), 0)     AS assigned,
               COALESCE(SUM(d.status = 'Under Repair'), 0) AS under_repair,
               COALESCE(SUM(d.status = 'Retired'), 0)      AS retired
        FROM asset_catalog ac
        LEFT JOIN devices d ON d.catalog_id = ac.id AND d.is_deleted = FALSE
        GROUP BY ac.id
        ORDER BY ac.category, ac.brand, ac.model
    """)
    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
            elif isinstance(v, type(None)):
                r[k] = 0
            elif hasattr(v, '__int__') and k not in ('category', 'brand', 'model', 'specifications', 'vendor', 'notes'):
                r[k] = int(v)
    return rows


def create_catalog_entry(data: dict) -> int:
    """Add a new catalog SKU."""
    category = data.get("category", "Other")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}")

    return execute_query("""
        INSERT INTO asset_catalog (category, brand, model, specifications, unit_cost, vendor, low_stock_threshold, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        category, data["brand"], data["model"],
        data.get("specifications"), data.get("unit_cost"),
        data.get("vendor"), data.get("low_stock_threshold", 3),
        data.get("notes"),
    ), commit=True)


def update_catalog_entry(catalog_id: int, data: dict) -> bool:
    """Update an existing catalog entry."""
    existing = execute_single("SELECT id FROM asset_catalog WHERE id = %s", (catalog_id,))
    if not existing:
        return False

    if "category" in data and data["category"] not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{data['category']}'. Must be one of: {', '.join(VALID_CATEGORIES)}")

    fields, params = [], []
    updatable = ["category", "brand", "model", "specifications", "unit_cost", "vendor", "low_stock_threshold", "notes"]
    for f in updatable:
        if f in data:
            fields.append(f"{f} = %s")
            params.append(data[f])

    if not fields:
        return True  # Nothing to update

    params.append(catalog_id)
    execute_query(f"UPDATE asset_catalog SET {', '.join(fields)} WHERE id = %s", tuple(params), commit=True)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Device Status Change (with stock logging)
# ─────────────────────────────────────────────────────────────────────────────

def update_device_status(device_id: int, new_status: str, performed_by: str, notes: str = None) -> dict:
    """
    Change a device's status with validation and stock-change logging.
    Valid transitions:
      Available → Assigned, Under Repair, Retired
      Assigned  → Available (return), Under Repair
      Under Repair → Available, Retired
      Retired   → (no transitions — end of life)
    """
    valid_statuses = ("Available", "Assigned", "Under Repair", "Retired")
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {', '.join(valid_statuses)}")

    device = execute_single("SELECT * FROM devices WHERE id = %s AND is_deleted = FALSE", (device_id,))
    if not device:
        raise ValueError("Device not found or already deleted.")

    old_status = device["status"]
    if old_status == new_status:
        raise ValueError(f"Device is already '{new_status}'.")

    if old_status == "Retired":
        raise ValueError("Cannot change status of a retired device.")

    # Map transition to stock log action
    action_map = {
        ("Available", "Under Repair"): "repair_in",
        ("Under Repair", "Available"): "repair_out",
        ("Available", "Retired"): "retired",
        ("Assigned", "Under Repair"): "repair_in",
        ("Under Repair", "Retired"): "retired",
    }
    action = action_map.get((old_status, new_status), "status_change")

    with Transaction() as cursor:
        cursor.execute("UPDATE devices SET status = %s WHERE id = %s", (new_status, device_id))
        cursor.execute("""
            INSERT INTO asset_stock_log (device_id, catalog_id, action, old_status, new_status, performed_by, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (device_id, device.get("catalog_id"), action, old_status, new_status, performed_by, notes))

    label = f"{device['brand']} {device['model']} (SN: {device['serial_number']})"
    logger.info(f"STOCK: {performed_by} changed device {device_id} ({label}) from {old_status} → {new_status}")

    return {"device_id": device_id, "old_status": old_status, "new_status": new_status, "action": action}


# ─────────────────────────────────────────────────────────────────────────────
# Asset Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

def get_asset_lifecycle(device_id: int) -> dict:
    """Full timeline of a device: stock log + assignment history."""
    device = execute_single("""
        SELECT d.*, ac.category, ac.vendor, ac.unit_cost
        FROM devices d
        LEFT JOIN asset_catalog ac ON d.catalog_id = ac.id
        WHERE d.id = %s
    """, (device_id,))
    if not device:
        return None

    for k, v in device.items():
        if hasattr(v, "isoformat"):
            device[k] = v.isoformat()

    stock_log = execute_query("""
        SELECT action, old_status, new_status, performed_by, notes, created_at
        FROM asset_stock_log WHERE device_id = %s ORDER BY created_at ASC
    """, (device_id,))

    assignments = execute_query("""
        SELECT employee_name, assigned_date, returned_date, acceptance_status
        FROM device_assignments WHERE device_id = %s ORDER BY assigned_date ASC
    """, (device_id,))

    for row in stock_log + assignments:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()

    return {"device": device, "stock_log": stock_log, "assignments": assignments}


# ─────────────────────────────────────────────────────────────────────────────
# Stock Reconciliation
# ─────────────────────────────────────────────────────────────────────────────

def reconcile_stock() -> dict:
    """
    Compare device statuses against assignment state.
    Flags inconsistencies like:
      - Device status = 'Assigned' but no active assignment row
      - Device status = 'Available' but has an active (non-returned) assignment
    """
    # Devices marked Assigned but with no active assignment
    orphaned_assigned = execute_query("""
        SELECT d.id, d.brand, d.model, d.serial_number, d.status
        FROM devices d
        LEFT JOIN device_assignments da ON d.id = da.device_id AND da.returned_date IS NULL
        WHERE d.status = 'Assigned' AND d.is_deleted = FALSE AND da.id IS NULL
    """)

    # Devices marked Available but with an active assignment
    ghost_available = execute_query("""
        SELECT d.id, d.brand, d.model, d.serial_number, d.status,
               da.employee_name, da.assigned_date
        FROM devices d
        JOIN device_assignments da ON d.id = da.device_id AND da.returned_date IS NULL
        WHERE d.status = 'Available' AND d.is_deleted = FALSE
    """)

    for row in orphaned_assigned + ghost_available:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()

    return {
        "consistent": len(orphaned_assigned) == 0 and len(ghost_available) == 0,
        "orphaned_assigned": orphaned_assigned,
        "ghost_available": ghost_available,
        "total_issues": len(orphaned_assigned) + len(ghost_available),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Stock Log Helper (used by device_service.py)
# ─────────────────────────────────────────────────────────────────────────────

def log_stock_event(device_id: int, catalog_id, action: str, performed_by: str,
                    old_status: str = None, new_status: str = None, notes: str = None):
    """Insert an event into the asset_stock_log. Non-critical — logs but doesn't fail."""
    try:
        execute_query("""
            INSERT INTO asset_stock_log (device_id, catalog_id, action, old_status, new_status, performed_by, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (device_id, catalog_id, action, old_status, new_status, performed_by, notes), commit=True)
    except Exception as e:
        logger.warning(f"Failed to log stock event for device {device_id}: {e}")
