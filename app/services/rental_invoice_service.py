from app.models.database import execute_query, execute_single, Transaction
from datetime import datetime, date, timedelta
import calendar
import logging

logger = logging.getLogger(__name__)

def _generate_next_invoice_number(cursor, today_str: str) -> str:
    """
    Generate the next unique invoice number for today using row-level locking.
    Format: RNT-YYYYMMDD-NNNN (e.g., RNT-20260830-0001)
    """
    latest = execute_single(
        """
        SELECT invoice_number 
        FROM rental_invoices 
        WHERE invoice_number LIKE %s 
        ORDER BY invoice_number DESC 
        LIMIT 1 
        FOR UPDATE
        """,
        (f"RNT-{today_str}-%",),
        cursor=cursor
    )

    next_seq = 1
    if latest and latest.get("invoice_number"):
        try:
            raw_num = str(latest["invoice_number"]).strip()
            seq_part = raw_num.split("-")[-1]
            next_seq = int(seq_part) + 1
        except (ValueError, IndexError):
            cnt = execute_single(
                "SELECT COUNT(*) AS count FROM rental_invoices WHERE invoice_number LIKE %s",
                (f"RNT-{today_str}-%",),
                cursor=cursor
            )
            next_seq = (cnt["count"] if cnt else 0) + 1

    return f"RNT-{today_str}-{next_seq:04d}"


def check_and_generate_invoices():
    """Daily job to check all active rental assets and auto-generate invoices if due in <= 7 days."""
    today = date.today()
    cutoff_date = today + timedelta(days=7)

    # Fetch active rented devices
    devices = execute_query("""
        SELECT id, brand, model, device_type, vendor_name, rental_start_date, rental_cost, next_due_date
        FROM devices
        WHERE ownership_type = 'Rented'
          AND rental_cost_frequency = 'Monthly'
          AND is_deleted = FALSE
    """)

    for d in devices:
        start_date_str = d.get('rental_start_date')
        if not start_date_str:
            continue
        try:
            if isinstance(start_date_str, str):
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                start_dt = start_date_str
        except Exception as e:
            logger.error(f"Error parsing rental_start_date for device {d['id']}: {e}")
            continue

        # Loop to generate all invoices up to cutoff_date
        current_due = start_dt
        while current_due <= cutoff_date:
            # Check if invoice already exists for this due_date
            existing = execute_single("""
                SELECT id FROM rental_invoices
                WHERE device_id = %s AND due_date = %s
            """, (d['id'], current_due))

            if not existing:
                today_str = today.strftime('%Y%m%d')
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        with Transaction() as cursor:
                            # Double-check with lock inside the transaction
                            existing_in_tx = execute_single(
                                "SELECT id FROM rental_invoices WHERE device_id = %s AND due_date = %s FOR UPDATE",
                                (d['id'], current_due),
                                cursor=cursor
                            )
                            if existing_in_tx:
                                break

                            invoice_num = _generate_next_invoice_number(cursor, today_str)

                            asset_name = f"{d['brand']} {d['model']}"
                            monthly_amt = float(d['rental_cost'] or 0)
                            gst_amt = round(monthly_amt * 0.18, 2)  # 18% GST
                            total_amt = monthly_amt + gst_amt

                            # Calculate Period
                            period_start = current_due
                            # Period end is 1 month minus 1 day after period_start
                            month = period_start.month + 1
                            year = period_start.year
                            if month > 12:
                                month = 1
                                year += 1
                            last_day = calendar.monthrange(year, month)[1]
                            period_end = date(year, month, min(period_start.day, last_day)) - timedelta(days=1)

                            cursor.execute("""
                                INSERT INTO rental_invoices (invoice_number, device_id, vendor_name, asset_name, device_type,
                                                             rental_start_date, rental_end_date, monthly_rental_amount, gst_amount,
                                                             total_amount, due_date, status, generated_date)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending', %s)
                            """, (invoice_num, d['id'], d['vendor_name'], asset_name, d['device_type'],
                                  period_start, period_end, monthly_amt, gst_amt, total_amt, current_due, today))

                            # Calculate Days Remaining
                            days_rem = (current_due - today).days

                            # Show notification in base bell feed for HR and Admins
                            cursor.execute("""
                                INSERT INTO notifications (employee_name, title, message, type)
                                SELECT DISTINCT u.employee_name, %s, %s, 'rental_invoice'
                                FROM users u
                                WHERE u.role IN ('hr', 'admin')
                            """, (
                                "Rental Invoice Generated",
                                f"Invoice {invoice_num} generated for {asset_name} (Vendor: {d['vendor_name']}). Amount: Rs. {total_amt}. Due: {current_due} ({days_rem} days remaining).",
                            ))
                        logger.info(f"Auto-generated invoice {invoice_num} for device {d['id']} due on {current_due}")
                        break
                    except Exception as ex:
                        if "Duplicate entry" in str(ex) or "1062" in str(ex):
                            logger.warning(f"Duplicate invoice number on attempt {attempt + 1}/{max_retries}, retrying: {ex}")
                            continue
                        else:
                            logger.error(f"Failed to auto-generate invoice for device {d['id']} due on {current_due}: {ex}")
                            break

            # Move to next month's due date
            month = current_due.month + 1
            year = current_due.year
            if month > 12:
                month = 1
                year += 1
            last_day = calendar.monthrange(year, month)[1]
            current_due = date(year, month, min(start_dt.day, last_day))

        # Update next_due_date column to the oldest unpaid invoice's due date
        oldest_unpaid = execute_single("""
            SELECT due_date FROM rental_invoices
            WHERE device_id = %s AND status = 'Pending'
            ORDER BY due_date ASC
            LIMIT 1
        """, (d['id'],))
        if oldest_unpaid:
            next_due = oldest_unpaid['due_date']
        else:
            # If all paid, point to next billing month after latest paid
            latest_paid = execute_single("""
                SELECT due_date FROM rental_invoices
                WHERE device_id = %s AND status = 'Paid'
                ORDER BY due_date DESC
                LIMIT 1
            """, (d['id'],))
            if latest_paid:
                paid_dt = latest_paid['due_date']
                if isinstance(paid_dt, str):
                    paid_dt = datetime.strptime(paid_dt, "%Y-%m-%d").date()
                month = paid_dt.month + 1
                year = paid_dt.year
                if month > 12:
                    month = 1
                    year += 1
                last_day = calendar.monthrange(year, month)[1]
                next_due = date(year, month, min(start_dt.day, last_day))
            else:
                next_due = start_dt
        
        execute_query("UPDATE devices SET next_due_date = %s WHERE id = %s", (next_due, d['id']), commit=True)

def get_invoices(filters: dict = None) -> list:
    """Query and filter rental invoices."""
    conditions = []
    params = []

    if filters:
        if filters.get("status"):
            if filters["status"] == "Overdue":
                conditions.append("ri.status = 'Pending' AND ri.due_date < CURRENT_DATE()")
            elif filters["status"] == "Upcoming":
                conditions.append("ri.status = 'Pending' AND ri.due_date BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 7 DAY)")
            else:
                conditions.append("ri.status = %s")
                params.append(filters["status"])
        if filters.get("device_id"):
            conditions.append("ri.device_id = %s")
            params.append(filters["device_id"])
        if filters.get("vendor"):
            conditions.append("ri.vendor_name = %s")
            params.append(filters["vendor"])
        if filters.get("search"):
            conditions.append("(ri.vendor_name LIKE %s OR ri.asset_name LIKE %s OR ri.invoice_number LIKE %s)")
            s = f"%{filters['search']}%"
            params.extend([s, s, s])

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = execute_query(f"""
        SELECT ri.*, d.serial_number, d.asset_id AS custom_asset_id
        FROM rental_invoices ri
        JOIN devices d ON ri.device_id = d.id
        {where_clause}
        ORDER BY ri.due_date DESC
    """, tuple(params) if params else None)

    for r in rows:
        for k, v in r.items():
            if hasattr(v, 'isoformat'):
                r[k] = v.isoformat()
            if isinstance(v, float) or hasattr(v, 'as_tuple'):  # Handle decimal fields
                r[k] = float(v)
    return rows

def pay_invoice(invoice_id: int, payment_data: dict) -> dict:
    """Mark an invoice as Paid, record payment history, and update device next_due_date."""
    # 1. Fetch current invoice details
    invoice = execute_single("SELECT * FROM rental_invoices WHERE id = %s", (invoice_id,))
    if not invoice:
        raise ValueError("Invoice not found")
    if invoice["status"] == "Paid":
        raise ValueError("Invoice is already marked as paid")

    pay_date = payment_data.get("payment_date") or date.today().isoformat()
    pay_mode = payment_data.get("payment_mode") or "Bank Transfer"
    ref_num = payment_data.get("reference_number")
    remarks = payment_data.get("remarks")

    with Transaction() as cursor:
        # Update Invoice Record
        cursor.execute("""
            UPDATE rental_invoices
            SET status = 'Paid',
                payment_date = %s,
                payment_mode = %s,
                reference_number = %s,
                remarks = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (pay_date, pay_mode, ref_num, remarks, invoice_id))

        # Insert into Payment History
        cursor.execute("""
            INSERT INTO rental_payments (invoice_id, device_id, payment_date, amount, payment_mode, reference_number, remarks)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (invoice_id, invoice["device_id"], pay_date, invoice["total_amount"], pay_mode, ref_num, remarks))

        # Calculate new next due date from oldest unpaid or +1 month from current due
        cursor.execute("""
            SELECT due_date FROM rental_invoices
            WHERE device_id = %s AND status = 'Pending' AND id != %s
            ORDER BY due_date ASC
            LIMIT 1
        """, (invoice["device_id"], invoice_id))
        oldest_unpaid = cursor.fetchone()
        
        if oldest_unpaid:
            next_due = oldest_unpaid["due_date"]
            if isinstance(next_due, str):
                next_due = datetime.strptime(next_due, "%Y-%m-%d").date()
        else:
            # Advance +1 month from current due date
            current_due = invoice["due_date"]
            if isinstance(current_due, str):
                current_due = datetime.strptime(current_due, "%Y-%m-%d").date()
            month = current_due.month + 1
            year = current_due.year
            if month > 12:
                month = 1
                year += 1
            last_day = calendar.monthrange(year, month)[1]
            day = min(current_due.day, last_day)
            next_due = date(year, month, day)

        cursor.execute("""
            UPDATE devices
            SET next_due_date = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (next_due, invoice["device_id"]))

        # Remove active notification link matching this invoice
        # Remove active notification matching this invoice
        cursor.execute("""
            DELETE FROM notifications 
            WHERE type = 'rental_invoice' 
              AND message LIKE %s
        """, (f"%{invoice['invoice_number']}%",))

    return {
        "success": True,
        "next_due_date": next_due.isoformat(),
        "invoice_number": invoice["invoice_number"]
    }

def get_invoice_history(device_id: str) -> dict:
    """Return full invoice and payment history for a rental asset."""
    invoices = execute_query("""
        SELECT * FROM rental_invoices
        WHERE device_id = %s
        ORDER BY due_date DESC
    """, (device_id,))
    
    payments = execute_query("""
        SELECT rp.*, ri.invoice_number
        FROM rental_payments rp
        JOIN rental_invoices ri ON rp.invoice_id = ri.id
        WHERE rp.device_id = %s
        ORDER BY rp.payment_date DESC
    """, (device_id,))

    for item in invoices + payments:
        for k, v in item.items():
            if hasattr(v, 'isoformat'):
                item[k] = v.isoformat()
            if isinstance(v, float) or hasattr(v, 'as_tuple'):
                item[k] = float(v)

    return {
        "invoices": invoices,
        "payments": payments
    }

def get_invoice_dashboard_stats() -> dict:
    """Return the counts and totals for dashboard widgets."""
    today = date.today()
    upcoming_limit = today + timedelta(days=7)

    # 1. Upcoming payments count (due in next 7 days, Pending)
    upcoming = execute_single("""
        SELECT COUNT(*) AS cnt 
        FROM rental_invoices 
        WHERE status = 'Pending' AND due_date BETWEEN %s AND %s
    """, (today, upcoming_limit))

    # 2. Overdue payments count (Pending and due_date < today)
    overdue = execute_single("""
        SELECT COUNT(*) AS cnt 
        FROM rental_invoices 
        WHERE status = 'Pending' AND due_date < %s
    """, (today,))

    # 3. Total monthly rental cost (sum of cost for all active Rented assets)
    cost = execute_single("""
        SELECT SUM(rental_cost) AS total 
        FROM devices 
        WHERE ownership_type = 'Rented' 
          AND rental_cost_frequency = 'Monthly' 
          AND is_deleted = FALSE
    """)

    # 4. Pending invoice amount (sum of total_amount for Pending invoices)
    pending_amt = execute_single("""
        SELECT SUM(total_amount) AS total 
        FROM rental_invoices 
        WHERE status = 'Pending'
    """)

    # 5. Lists for rendering on dashboard
    upcoming_list = execute_query("""
        SELECT invoice_number, vendor_name, asset_name, total_amount, due_date
        FROM rental_invoices
        WHERE status = 'Pending' AND due_date BETWEEN %s AND %s
        ORDER BY due_date ASC
    """, (today, upcoming_limit))

    overdue_list = execute_query("""
        SELECT invoice_number, vendor_name, asset_name, total_amount, due_date
        FROM rental_invoices
        WHERE status = 'Pending' AND due_date < %s
        ORDER BY due_date ASC
    """, (today,))

    for item in upcoming_list + overdue_list:
        for k, v in item.items():
            if hasattr(v, 'isoformat'):
                item[k] = v.isoformat()
            if isinstance(v, float) or hasattr(v, 'as_tuple'):
                item[k] = float(v)

    return {
        "upcoming_count": upcoming["cnt"] if upcoming else 0,
        "overdue_count": overdue["cnt"] if overdue else 0,
        "total_monthly_cost": float(cost["total"] or 0) if cost else 0.0,
        "pending_amount": float(pending_amt["total"] or 0) if pending_amt else 0.0,
        "upcoming_payments": upcoming_list,
        "overdue_payments": overdue_list
    }
