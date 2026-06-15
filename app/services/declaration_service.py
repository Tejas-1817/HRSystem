"""
Declaration Service — Onboarding Declaration Business Logic
============================================================
Encapsulates validation, flatten/unflatten, CRUD, and workflow
operations for the onboarding_declaration and onboarding_references
tables.  Keeps SQL out of route handlers.

Public API
----------
- validate_declaration_payload(data, is_submit=False) → (errors, cleaned)
- flatten_education(education_list)   → dict
- flatten_employment(employment_list) → dict
- unflatten_education(row)            → list[dict]
- unflatten_employment(row)           → list[dict]
- get_declaration_by_joinee(joinee_id, cursor=None)       → dict | None
- get_references_by_declaration(declaration_id, cursor=None) → list[dict]
- build_declaration_response(joinee_id, cursor=None)      → dict | None
- insert_declaration(joinee_id, data, cursor)              → int (new id)
- update_declaration(declaration_id, data, cursor)         → None
- replace_references(declaration_id, joinee_id, refs, cursor) → None
- submit_declaration(declaration_id, cursor)               → None
- review_declaration(declaration_id, status, hr_notes, hr_user_id, cursor) → None
- check_all_documents_approved(joinee_id, cursor=None)    → bool
"""

import logging
from app.models.database import execute_single, execute_query

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Constants
# ═════════════════════════════════════════════════════════════════════════════

# Column keys for each education slot (matches onboarding_declaration schema)
_EDU_FIELDS = (
    "qualification", "specialization", "college_name",
    "address", "university", "period", "program",
)

# Column keys for each employment slot
_EMP_FIELDS = (
    "company_name", "employee_id", "address", "doj", "lwd",
    "city", "designation", "state", "remuneration",
    "contact1", "reported_to", "contact2",
    "reported_person_designation", "reason_for_leaving",
)

MAX_EDUCATION = 3
MAX_EMPLOYMENT = 6
MIN_REFERENCES_ON_SUBMIT = 3
MAX_REFERENCES = 6

# All scalar declaration columns that can be set directly from request payload.
# Excludes id, joinee_id, status, workflow/admin fields, and edu/emp columns.
_DECLARATION_SCALAR_FIELDS = (
    "full_name", "contact_no", "email_id", "father_name", "gender",
    "actual_dob", "certificate_dob",
    # Current address
    "current_address", "current_landmark", "current_landline",
    "current_mobile", "current_period_of_stay", "current_nature_of_residence",
    # Permanent address
    "permanent_address", "permanent_landmark", "permanent_landline",
    "permanent_mobile", "permanent_period_of_stay", "permanent_nature_of_residence",
    # Identity
    "pan_number", "aadhar_number",
    "passport_name", "passport_issue_date", "passport_expiry_date",
    "passport_place_of_issue", "other_id_details",
    # Other details
    "has_service_bond", "has_service_bond_details",
    "has_criminal_record", "has_criminal_record_details",
    "knows_company_employee", "knows_company_employee_details",
    # Onsite
    "onsite_details",
    # Declaration authorization
    "declaration_full_name", "declaration_date",
    "declaration_place", "declaration_agreed",
)


# ═════════════════════════════════════════════════════════════════════════════
# Validation
# ═════════════════════════════════════════════════════════════════════════════

def validate_declaration_payload(data, is_submit=False):
    """
    Validate the incoming declaration payload.

    Returns (errors: dict, cleaned: dict).
    When *is_submit* is True, references minimum (3) is enforced.
    For draft saves, reference count is not validated.
    """
    errors = {}

    # --- Education cap ---
    education = data.get("education") or []
    if not isinstance(education, list):
        errors["education"] = "Must be a list"
    elif len(education) > MAX_EDUCATION:
        errors["education"] = f"Maximum {MAX_EDUCATION} education entries allowed"

    # --- Employment cap ---
    employment = data.get("employment") or []
    if not isinstance(employment, list):
        errors["employment"] = "Must be a list"
    elif len(employment) > MAX_EMPLOYMENT:
        errors["employment"] = f"Maximum {MAX_EMPLOYMENT} employment entries allowed"

    # --- References ---
    references = data.get("references") or []
    if not isinstance(references, list):
        errors["references"] = "Must be a list"
    else:
        if len(references) > MAX_REFERENCES:
            errors["references"] = f"Maximum {MAX_REFERENCES} references allowed"
        if is_submit and len(references) < MIN_REFERENCES_ON_SUBMIT:
            errors["references"] = (
                f"Minimum {MIN_REFERENCES_ON_SUBMIT} professional references "
                f"required for submission"
            )

    return errors, data


# ═════════════════════════════════════════════════════════════════════════════
# Flatten / Unflatten — Education
# ═════════════════════════════════════════════════════════════════════════════

def flatten_education(education_list):
    """
    Convert a list of education dicts (max 3) into flat column values.

    Input:  [{"qualification": "B.Tech", "specialization": "CS", ...}, ...]
    Output: {"edu1_qualification": "B.Tech", "edu1_specialization": "CS", ...,
             "edu2_qualification": None, ...}
    """
    result = {}
    for slot in range(1, MAX_EDUCATION + 1):
        entry = education_list[slot - 1] if slot <= len(education_list) else {}
        for field in _EDU_FIELDS:
            key = f"edu{slot}_{field}"
            result[key] = entry.get(field) or None
    return result


def unflatten_education(row):
    """
    Extract edu1_*, edu2_*, edu3_* columns from a declaration row into a list
    of education dicts.  Empty slots (all None) are omitted.
    """
    entries = []
    for slot in range(1, MAX_EDUCATION + 1):
        entry = {}
        has_data = False
        for field in _EDU_FIELDS:
            key = f"edu{slot}_{field}"
            val = row.get(key)
            entry[field] = val
            if val is not None:
                has_data = True
        if has_data:
            entries.append(entry)
    return entries


# ═════════════════════════════════════════════════════════════════════════════
# Flatten / Unflatten — Employment
# ═════════════════════════════════════════════════════════════════════════════

def flatten_employment(employment_list):
    """
    Convert a list of employment dicts (max 6) into flat column values.
    """
    result = {}
    for slot in range(1, MAX_EMPLOYMENT + 1):
        entry = employment_list[slot - 1] if slot <= len(employment_list) else {}
        for field in _EMP_FIELDS:
            key = f"emp{slot}_{field}"
            result[key] = entry.get(field) or None
    return result


def unflatten_employment(row):
    """
    Extract emp1_* … emp6_* columns from a declaration row into a list
    of employment dicts.  Empty slots are omitted.
    """
    entries = []
    for slot in range(1, MAX_EMPLOYMENT + 1):
        entry = {}
        has_data = False
        for field in _EMP_FIELDS:
            key = f"emp{slot}_{field}"
            val = row.get(key)
            entry[field] = val
            if val is not None:
                has_data = True
        if has_data:
            entries.append(entry)
    return entries


# ═════════════════════════════════════════════════════════════════════════════
# Data Access — Read
# ═════════════════════════════════════════════════════════════════════════════

def get_declaration_by_joinee(joinee_id, cursor=None):
    """Fetch the latest declaration row for a joinee."""
    query = """
        SELECT *
        FROM   onboarding_declaration
        WHERE  joinee_id = %s
        ORDER  BY id DESC
        LIMIT  1
    """
    if cursor:
        cursor.execute(query, (joinee_id,))
        return cursor.fetchone()
    return execute_single(query, (joinee_id,))


def get_references_by_declaration(declaration_id, cursor=None):
    """Fetch all professional references for a declaration, ordered by sort_order."""
    query = """
        SELECT id, ref_name, ref_designation, ref_phone, ref_email,
               ref_company_name, candidate_designation, sort_order
        FROM   onboarding_references
        WHERE  declaration_id = %s
        ORDER  BY sort_order
    """
    if cursor:
        cursor.execute(query, (declaration_id,))
        return cursor.fetchall()
    return execute_query(query, (declaration_id,)) or []


# ═════════════════════════════════════════════════════════════════════════════
# Response Builder
# ═════════════════════════════════════════════════════════════════════════════

def build_declaration_response(joinee_id, cursor=None):
    """
    Compose the full API response dict for a joinee's declaration.

    Returns dict with:
      - All scalar declaration fields
      - education: [] (unflattened)
      - employment: [] (unflattened)
      - references: []
      - Workflow fields (status, submitted_at, hr_notes, etc.)

    Returns None if no declaration exists.
    """
    declaration = get_declaration_by_joinee(joinee_id, cursor=cursor)
    if not declaration:
        return None

    # Build structured education / employment arrays
    education = unflatten_education(declaration)
    employment = unflatten_employment(declaration)

    # Fetch references
    references = get_references_by_declaration(declaration["id"], cursor=cursor)

    # Build clean response — pick scalar fields, add structured arrays
    response = {}
    for field in _DECLARATION_SCALAR_FIELDS:
        val = declaration.get(field)
        # Serialize date/datetime objects to ISO strings
        if val is not None and hasattr(val, "isoformat"):
            val = val.isoformat()
        response[field] = val

    # Workflow / admin fields
    for wf_field in ("id", "joinee_id", "status", "submitted_at",
                      "hr_notes", "hr_reviewed_by", "hr_reviewed_at",
                      "created_at", "updated_at"):
        val = declaration.get(wf_field)
        if val is not None and hasattr(val, "isoformat"):
            val = val.isoformat()
        response[wf_field] = val

    response["education"] = education
    response["employment"] = employment
    response["references"] = _serialize_list(references)

    return response


def _serialize_list(rows):
    """Serialize a list of dicts, converting date/datetime to ISO strings."""
    result = []
    for row in rows:
        cleaned = {}
        for k, v in row.items():
            if v is not None and hasattr(v, "isoformat"):
                v = v.isoformat()
            cleaned[k] = v
        result.append(cleaned)
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Data Access — Write (all require a Transaction cursor)
# ═════════════════════════════════════════════════════════════════════════════

def _build_declaration_columns(data):
    """
    Extract all writable declaration columns from request data,
    including flattened education and employment.

    Returns (columns: list[str], values: list).
    """
    columns = []
    values = []

    # Scalar fields
    for field in _DECLARATION_SCALAR_FIELDS:
        if field in data:
            columns.append(field)
            val = data[field]
            # Convert empty strings to None for nullable DB columns
            if val == "":
                val = None
            values.append(val)

    # Flattened education
    edu_flat = flatten_education(data.get("education") or [])
    for col, val in edu_flat.items():
        columns.append(col)
        values.append(val)

    # Flattened employment
    emp_flat = flatten_employment(data.get("employment") or [])
    for col, val in emp_flat.items():
        columns.append(col)
        values.append(val)

    return columns, values


def insert_declaration(joinee_id, data, cursor):
    """
    INSERT a new declaration row.  Returns the new declaration ID.
    Status is set to DRAFT.
    """
    columns, values = _build_declaration_columns(data)

    # Prepend joinee_id and status
    columns = ["joinee_id", "status"] + columns
    values = [joinee_id, "DRAFT"] + values

    placeholders = ", ".join(["%s"] * len(values))
    col_names = ", ".join(columns)

    query = f"INSERT INTO onboarding_declaration ({col_names}) VALUES ({placeholders})"
    cursor.execute(query, tuple(values))
    return cursor.lastrowid


def update_declaration(declaration_id, data, cursor):
    """
    UPDATE an existing declaration row (scalar + edu + emp fields only).
    Does NOT change status or workflow fields.
    """
    columns, values = _build_declaration_columns(data)

    if not columns:
        return

    set_clause = ", ".join(f"{col} = %s" for col in columns)
    values.append(declaration_id)

    query = f"UPDATE onboarding_declaration SET {set_clause} WHERE id = %s"
    cursor.execute(query, tuple(values))


def replace_references(declaration_id, joinee_id, references, cursor):
    """
    Delete all existing references for a declaration and insert the new set.
    Each reference gets a sort_order (1-based).
    """
    cursor.execute(
        "DELETE FROM onboarding_references WHERE declaration_id = %s",
        (declaration_id,),
    )

    if not references:
        return

    for idx, ref in enumerate(references, start=1):
        cursor.execute(
            """
            INSERT INTO onboarding_references
                (declaration_id, joinee_id, ref_name, ref_designation,
                 ref_phone, ref_email, ref_company_name,
                 candidate_designation, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                declaration_id,
                joinee_id,
                ref.get("ref_name"),
                ref.get("ref_designation"),
                ref.get("ref_phone"),
                ref.get("ref_email"),
                ref.get("ref_company_name"),
                ref.get("candidate_designation"),
                idx,
            ),
        )


# ═════════════════════════════════════════════════════════════════════════════
# Workflow Operations (require a Transaction cursor)
# ═════════════════════════════════════════════════════════════════════════════

def submit_declaration(declaration_id, cursor):
    """Set declaration status to SUBMITTED and record timestamp."""
    cursor.execute(
        """
        UPDATE onboarding_declaration
        SET    status = 'SUBMITTED', submitted_at = NOW()
        WHERE  id = %s
        """,
        (declaration_id,),
    )


def review_declaration(declaration_id, status, hr_notes, hr_user_id, cursor):
    """
    Record HR review on a declaration.
    Sets status, hr_notes, hr_reviewed_by, hr_reviewed_at.
    """
    cursor.execute(
        """
        UPDATE onboarding_declaration
        SET    status = %s,
               hr_notes = %s,
               hr_reviewed_by = %s,
               hr_reviewed_at = NOW()
        WHERE  id = %s
        """,
        (status, hr_notes, hr_user_id, declaration_id),
    )


def check_all_documents_approved(joinee_id, cursor=None):
    """
    Returns True if ALL uploaded onboarding_documents for a joinee have
    verification_status = 'APPROVED'.  Returns False if there are no
    documents or any are not yet approved.
    """
    query = """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN verification_status = 'APPROVED' THEN 1 ELSE 0 END) AS approved
        FROM   onboarding_documents
        WHERE  joinee_id = %s
    """
    if cursor:
        cursor.execute(query, (joinee_id,))
        row = cursor.fetchone()
    else:
        row = execute_single(query, (joinee_id,))

    if not row or row["total"] == 0:
        return False
    return row["approved"] == row["total"]
