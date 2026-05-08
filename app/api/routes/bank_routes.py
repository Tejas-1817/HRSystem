from flask import Blueprint, request, jsonify
import re
from app.models.database import execute_query, execute_single, get_connection
from app.api.middleware.auth import token_required, role_required

bank_bp = Blueprint('bank', __name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IFSC_REGEX = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')

def _validate_fields(data):
    """Returns an error string if required fields are missing or invalid,
    otherwise returns None."""
    required = ('account_holder_name', 'bank_name', 'account_number',
                'ifsc_code', 'branch_name')
    missing = [f for f in required if not data.get(f, '').strip()]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    if not IFSC_REGEX.match(data['ifsc_code'].upper()):
        return ("Invalid IFSC code format. Expected 11 characters: "
                "4 letters, '0', then 6 alphanumeric characters (e.g. SBIN0001234).")
    if not re.match(r'^\d{9,18}$', data['account_number']):
        return "Account number must be 9–18 digits."
    return None


def _mask_account(account_number: str) -> str:
    """Returns the account number with only the last 4 digits visible."""
    if len(account_number) <= 4:
        return account_number
    return '*' * (len(account_number) - 4) + account_number[-4:]


# ---------------------------------------------------------------------------
# Employee: Add or Update own bank details
# ---------------------------------------------------------------------------

@bank_bp.route('/my', methods=['POST', 'PUT'])
@token_required
def upsert_my_bank_details(current_user):
    """
    POST / PUT /bank/my
    Employee adds or updates their own bank details.
    Managers are explicitly blocked.
    """
    if current_user['role'] == 'manager':
        return jsonify({'success': False,
                        'error': 'Managers cannot submit bank details through this endpoint.'}), 403

    data = request.get_json() or {}
    error = _validate_fields(data)
    if error:
        return jsonify({'success': False, 'error': error}), 400

    emp_name = current_user['employee_name']
    existing = execute_single('SELECT id FROM bank_details WHERE employee_name=%s', (emp_name,))

    if existing:
        # Update – reset status to 'completed' since data changed
        execute_query("""
            UPDATE bank_details
            SET account_holder_name=%s, bank_name=%s, account_number=%s,
                ifsc_code=%s, branch_name=%s, status='completed',
                verified_by=NULL, verified_at=NULL
            WHERE employee_name=%s
        """, (
            data['account_holder_name'].strip(),
            data['bank_name'].strip(),
            data['account_number'].strip(),
            data['ifsc_code'].strip().upper(),
            data['branch_name'].strip(),
            emp_name,
        ), commit=True)
        return jsonify({'success': True, 'message': 'Bank details updated successfully.'}), 200
    else:
        execute_query("""
            INSERT INTO bank_details
                (employee_name, account_holder_name, bank_name, account_number,
                 ifsc_code, branch_name, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'completed')
        """, (
            emp_name,
            data['account_holder_name'].strip(),
            data['bank_name'].strip(),
            data['account_number'].strip(),
            data['ifsc_code'].strip().upper(),
            data['branch_name'].strip(),
        ), commit=True)
        return jsonify({'success': True, 'message': 'Bank details submitted successfully.'}), 201


# ---------------------------------------------------------------------------
# Employee: View own bank details (masked account number)
# ---------------------------------------------------------------------------

@bank_bp.route('/my', methods=['GET'])
@token_required
def get_my_bank_details(current_user):
    """
    GET /bank/my
    Employee views their own bank details.
    Account number is masked — only last 4 digits shown.
    """
    row = execute_single(
        'SELECT * FROM bank_details WHERE employee_name=%s',
        (current_user['employee_name'],)
    )
    if not row:
        return jsonify({
            'success': True,
            'bank_details': None,
            'status': 'pending',
            'message': 'No bank details submitted yet.'
        }), 200

    row['account_number'] = _mask_account(row['account_number'])
    return jsonify({'success': True, 'bank_details': row}), 200


# ---------------------------------------------------------------------------
# HR: View ALL bank details (unmasked)
# ---------------------------------------------------------------------------

@bank_bp.route('/', methods=['GET'])
@role_required(['hr'])
def get_all_bank_details(current_user):
    """
    GET /bank/
    HR-only: Returns all employee bank details with full account numbers.
    """
    rows = execute_query(
        'SELECT * FROM bank_details ORDER BY status, employee_name'
    )
    return jsonify({'success': True, 'bank_details': rows, 'total': len(rows)}), 200


# ---------------------------------------------------------------------------
# HR: View single employee's bank details (unmasked)
# ---------------------------------------------------------------------------

@bank_bp.route('/<string:employee_name>', methods=['GET'])
@role_required(['hr'])
def get_employee_bank_details(current_user, employee_name):
    """
    GET /bank/<employee_name>
    HR-only: View one employee's full bank details.
    """
    row = execute_single(
        'SELECT * FROM bank_details WHERE employee_name=%s', (employee_name,)
    )
    if not row:
        return jsonify({'success': False, 'error': 'No bank details found for this employee.'}), 404
    return jsonify({'success': True, 'bank_details': row}), 200


# ---------------------------------------------------------------------------
# HR: Verify bank details
# ---------------------------------------------------------------------------

@bank_bp.route('/verify/<string:employee_name>', methods=['PATCH'])
@role_required(['hr'])
def verify_bank_details(current_user, employee_name):
    """
    PATCH /bank/verify/<employee_name>
    HR-only: Marks the employee's bank details as verified.
    Logs the action to audit_logs.
    """
    row = execute_single(
        'SELECT id, status FROM bank_details WHERE employee_name=%s', (employee_name,)
    )
    if not row:
        return jsonify({'success': False, 'error': 'No bank details found for this employee.'}), 404
    if row['status'] == 'verified':
        return jsonify({'success': True, 'message': 'Already verified.'}), 200

    execute_query("""
        UPDATE bank_details
        SET status='verified', verified_by=%s, verified_at=NOW()
        WHERE employee_name=%s
    """, (current_user['employee_name'], employee_name), commit=True)

    # Audit log
    hr_user = execute_single('SELECT id FROM users WHERE employee_name=%s',
                             (current_user['employee_name'],))
    if hr_user:
        execute_query(
            'INSERT INTO audit_logs (user_id, event_type, description) VALUES (%s, %s, %s)',
            (hr_user['id'], 'bank_verification',
             f"HR {current_user['employee_name']} verified bank details for {employee_name}."),
            commit=True
        )

    return jsonify({
        'success': True,
        'message': f"Bank details for {employee_name} marked as verified."
    }), 200


# ---------------------------------------------------------------------------
# HR: Dashboard — employees with pending bank details
# ---------------------------------------------------------------------------

@bank_bp.route('/pending', methods=['GET'])
@role_required(['hr'])
def get_pending_bank_details(current_user):
    """
    GET /bank/pending
    HR-only: Returns employees who have NOT yet submitted bank details,
    plus those whose details are not yet verified.
    """
    submitted = execute_query(
        "SELECT employee_name, status FROM bank_details WHERE status != 'verified'"
    )
    return jsonify({'success': True, 'pending': submitted, 'total': len(submitted)}), 200


# ---------------------------------------------------------------------------
# HR: Delete bank details (e.g., employee left the company)
# ---------------------------------------------------------------------------

@bank_bp.route('/<string:employee_name>', methods=['DELETE'])
@role_required(['hr'])
def delete_bank_details(current_user, employee_name):
    """
    DELETE /bank/<employee_name>
    HR-only: Removes a bank record (e.g., on employee offboarding).
    """
    row = execute_single(
        'SELECT id FROM bank_details WHERE employee_name=%s', (employee_name,)
    )
    if not row:
        return jsonify({'success': False, 'error': 'No bank details found.'}), 404
    execute_query(
        'DELETE FROM bank_details WHERE employee_name=%s', (employee_name,), commit=True
    )
    return jsonify({'success': True, 'message': f'Bank details for {employee_name} deleted.'}), 200
