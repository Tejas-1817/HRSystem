"""
Leave Credit Service — Automatic Quarterly Leave Crediting
==========================================================
Phase 2: Quarter-calculation (pure function, zero DB side effects)
Phase 4: Transactional crediting logic (idempotent, uses DB)

Policy summary (confirmed in Phase 0):
  - Eligibility: Full Time employees only (Contract/Intern excluded)
  - Cycle: 3-month quarters based on date_of_joining, repeating indefinitely
  - Prorate: all-or-nothing — credit only when the quarter milestone is
    fully reached; partial quarters get nothing
  - Optional-leave pattern (Q-number mod 4):
      Q1, Q5, Q9, … (remainder 1)  → 1 optional leave
      Q2, Q4, Q6, Q8, … (even)     → 0 optional leaves
      Q3, Q7, Q11, … (remainder 3) → 1 optional leave
      i.e. optional = 0 if quarter_number is even, else 1

Credit amounts per quarter:
  Planned   → 3 leaves
  Unplanned → 1 leave
  Optional  → 1 leave (odd quarters only) or 0 (even quarters)
"""

from __future__ import annotations

from datetime import date
from typing import List, Dict, Any, Optional, Tuple

from dateutil.relativedelta import relativedelta

from app.models.database import execute_query, execute_single, Transaction

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLANNED_PER_QUARTER   = 3.0
UNPLANNED_PER_QUARTER = 1.0
# Optional alternates: 1 on odd quarter numbers, 0 on even
ELIGIBLE_EMPLOYMENT_TYPE = "Full Time"


# ---------------------------------------------------------------------------
# Phase 2 — Quarter-calculation (pure, no DB writes)
# ---------------------------------------------------------------------------

def _optional_for_quarter(quarter_number: int) -> float:
    """Return optional leave amount for a given 1-based quarter number.
    Pattern repeats every 4 quarters: Q1→1, Q2→0, Q3→1, Q4→0, Q5→1 …
    Implemented as: odd quarter_number → 1, even → 0.
    """
    return 1.0 if quarter_number % 2 == 1 else 0.0


def calculate_quarters_for_employee(
    date_of_joining: date,
    as_of_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Calculate every quarter milestone this employee has *fully reached*
    as of `as_of_date` (defaults to today).

    A quarter starts on the date_of_joining anniversary month-day,
    3 calendar months apart (using dateutil.relativedelta so month-end
    joining dates clamp correctly, e.g. Jan 31 + 3 months → Apr 30).

    Returns a list of dicts, each representing one completed quarter:
      {
        "quarter_number":         int,   # 1-based, repeating (Q5 = Year 2 Q1)
        "quarter_start":          date,
        "quarter_end":            date,  # day before next quarter_start
        "planned_to_credit":      float,
        "unplanned_to_credit":    float,
        "optional_to_credit":     float,
      }

    Returns an empty list if no quarters have been reached yet.
    """
    if as_of_date is None:
        as_of_date = date.today()

    completed: List[Dict[str, Any]] = []
    q_num = 0

    while True:
        q_num += 1
        q_start = date_of_joining + relativedelta(months=3 * (q_num - 1))
        q_end_exclusive = date_of_joining + relativedelta(months=3 * q_num)
        q_end = q_end_exclusive - relativedelta(days=1)  # inclusive end

        # Quarter milestone is the first day of the next quarter
        if q_end_exclusive > as_of_date:
            # This quarter's milestone has not been reached yet → stop
            break

        completed.append({
            "quarter_number":      q_num,
            "quarter_start":       q_start,
            "quarter_end":         q_end,
            "planned_to_credit":   PLANNED_PER_QUARTER,
            "unplanned_to_credit": UNPLANNED_PER_QUARTER,
            "optional_to_credit":  _optional_for_quarter(q_num),
        })

    return completed


# ---------------------------------------------------------------------------
# Phase 4 — Crediting logic (transactional, idempotent)
# ---------------------------------------------------------------------------

def _ensure_balance_row(cursor, employee_name: str, leave_type: str) -> None:
    """INSERT IGNORE a zero-balance row so subsequent UPDATE always hits a row."""
    cursor.execute("""
        INSERT IGNORE INTO leave_balance (employee_name, leave_type, total_leaves, used_leaves)
        VALUES (%s, %s, 0, 0)
    """, (employee_name, leave_type))


def credit_quarter_for_employee(
    employee_name: str,
    quarter: Dict[str, Any],
    credited_by: str = "system",
) -> Dict[str, Any]:
    """
    Credit one quarter for one employee inside a single DB transaction.

    Idempotency: the UNIQUE KEY (employee_name, quarter_number) on
    employee_leave_credit_log is the sole guard. A duplicate attempt
    raises IntegrityError → caught → returned as a clean skip (not an
    error), so re-running is always safe.

    Returns:
      {"status": "credited",   "quarter_number": int}  — new credit applied
      {"status": "skipped",    "quarter_number": int}  — already credited
      {"status": "failed",     "quarter_number": int, "error": str}
    """
    q_num    = quarter["quarter_number"]
    q_start  = quarter["quarter_start"]
    q_end    = quarter["quarter_end"]
    planned  = quarter["planned_to_credit"]
    unplanned= quarter["unplanned_to_credit"]
    optional = quarter["optional_to_credit"]

    try:
        with Transaction() as cursor:
            # Step 1: Insert into credit log (will fail on duplicate)
            try:
                cursor.execute("""
                    INSERT INTO employee_leave_credit_log
                        (employee_name, quarter_number, quarter_start, quarter_end,
                         planned_leaves_credited, unplanned_leaves_credited,
                         optional_leaves_credited, credited_by, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'SUCCESS')
                """, (employee_name, q_num, q_start, q_end,
                      planned, unplanned, optional, credited_by))
            except Exception as dup_err:
                # Unique constraint violation → already credited, skip cleanly
                if "Duplicate entry" in str(dup_err) or "1062" in str(dup_err):
                    return {"status": "skipped", "quarter_number": q_num}
                raise  # unexpected error — re-raise to outer handler

            # Step 2: Update balances (only reached if log insert succeeded)
            credits = [
                ("planned",   planned),
                ("unplanned", unplanned),
                ("optional",  optional),
            ]
            for leave_type, amount in credits:
                if amount <= 0:
                    continue
                _ensure_balance_row(cursor, employee_name, leave_type)
                cursor.execute("""
                    UPDATE leave_balance
                       SET total_leaves = total_leaves + %s
                     WHERE employee_name = %s AND leave_type = %s
                """, (amount, employee_name, leave_type))

        return {"status": "credited", "quarter_number": q_num}

    except Exception as e:
        return {"status": "failed", "quarter_number": q_num, "error": str(e)}


# ---------------------------------------------------------------------------
# Phase 5 helper — sweep function (used by scheduler + Phase 6 manual trigger)
# ---------------------------------------------------------------------------

def _get_eligible_employees() -> List[Dict[str, Any]]:
    """Return all active Full Time employees with their date_of_joining."""
    return execute_query("""
        SELECT e.name AS employee_name, e.date_of_joining
        FROM employees e
        JOIN users u ON u.employee_name = e.name
        WHERE u.is_active = TRUE
          AND e.employment_type = %s
          AND e.date_of_joining IS NOT NULL
        ORDER BY e.name
    """, (ELIGIBLE_EMPLOYMENT_TYPE,))


def _get_already_credited_quarters(employee_name: str) -> set:
    """Return set of quarter_numbers already credited for this employee."""
    rows = execute_query("""
        SELECT quarter_number
        FROM employee_leave_credit_log
        WHERE employee_name = %s AND status = 'SUCCESS'
    """, (employee_name,))
    return {r["quarter_number"] for r in rows}


def run_credit_sweep(
    as_of_date: Optional[date] = None,
    employee_name_filter: Optional[str] = None,
    credited_by: str = "system",
) -> Dict[str, Any]:
    """
    Sweep all eligible employees (or one specific employee) and credit any
    quarter that has been reached but not yet credited.

    This is the single function used by:
      - Phase 5 scheduler (daily job)
      - Phase 6 manual trigger (HR admin, with optional employee_name_filter)

    Returns a summary dict:
      {
        "employees_processed": int,
        "quarters_credited":   int,
        "quarters_skipped":    int,
        "quarters_failed":     int,
        "details": [...]          # per-employee per-quarter results
      }
    """
    if as_of_date is None:
        as_of_date = date.today()

    employees = _get_eligible_employees()
    if employee_name_filter:
        employees = [e for e in employees if e["employee_name"] == employee_name_filter]

    summary = {
        "employees_processed": len(employees),
        "quarters_credited":   0,
        "quarters_skipped":    0,
        "quarters_failed":     0,
        "details":             [],
    }

    for emp in employees:
        emp_name = emp["employee_name"]
        doj_raw  = emp["date_of_joining"]

        # Normalise date_of_joining (may come as str or date from DB)
        if isinstance(doj_raw, str):
            try:
                from datetime import datetime
                doj = datetime.strptime(doj_raw[:10], "%Y-%m-%d").date()
            except ValueError:
                summary["details"].append({
                    "employee": emp_name,
                    "error": f"Unparseable date_of_joining: {doj_raw}",
                })
                continue
        else:
            doj = doj_raw

        all_quarters     = calculate_quarters_for_employee(doj, as_of_date)
        credited_already = _get_already_credited_quarters(emp_name)
        pending          = [q for q in all_quarters if q["quarter_number"] not in credited_already]

        for q in pending:
            result = credit_quarter_for_employee(emp_name, q, credited_by=credited_by)
            summary["details"].append({"employee": emp_name, **result})
            if result["status"] == "credited":
                summary["quarters_credited"] += 1
            elif result["status"] == "skipped":
                summary["quarters_skipped"] += 1
            else:
                summary["quarters_failed"] += 1

    return summary
