"""
Migration 025: Permission Management Setup & Seed
"""

import sys
import os
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# The 76 dynamic permissions to be seeded
SEED_PERMISSIONS = [
    ("announcements.create", "announcements", "Create Announcement", "POST /", ["superadmin", "hr", "admin"]),
    ("announcements.update", "announcements", "Update Announcement", "PUT /<id>", ["superadmin", "hr", "admin"]),
    ("announcements.delete", "announcements", "Delete Announcement", "DELETE /<id>", ["superadmin", "hr", "admin"]),
    ("auth.register", "auth", "Register User", "POST /register", ["superadmin", "hr", "admin"]),
    ("auth.list_users", "auth", "List Users", "GET /users", ["superadmin", "hr", "admin"]),
    ("bank.list_all", "bank", "List All Bank Details", "GET /", ["superadmin", "hr", "admin"]),
    ("bank.get_employee", "bank", "Get Employee Bank Details", "GET /<employee_name>", ["superadmin", "hr", "admin"]),
    ("bank.verify", "bank", "Verify Bank Details", "PATCH /verify/<employee_name>", ["superadmin", "hr", "admin"]),
    ("bank.list_pending", "bank", "List Pending Bank Details", "GET /pending", ["superadmin", "hr", "admin"]),
    ("bank.delete", "bank", "Delete Bank Details", "DELETE /<employee_name>", ["superadmin", "hr", "admin"]),
    ("departments.create", "departments", "Create Department", "POST /departments", ["superadmin", "hr", "admin"]),
    ("departments.update", "departments", "Update Department", "PATCH /departments/<id>", ["superadmin", "hr", "admin"]),
    ("departments.deactivate", "departments", "Deactivate Department", "DELETE /departments/<id>", ["superadmin", "admin"]),
    ("designations.create", "designations", "Create Designation", "POST /designations", ["superadmin", "hr", "admin"]),
    ("designations.update", "designations", "Update Designation", "PATCH /designations/<id>", ["superadmin", "hr", "admin"]),
    ("designations.deactivate", "designations", "Deactivate Designation", "DELETE /designations/<id>", ["superadmin", "admin"]),
    ("devices.view_all", "devices", "View All Devices", "GET /", ["superadmin", "hr", "admin"]),
    ("devices.export", "devices", "Export Devices", "GET /export", ["superadmin", "hr", "admin"]),
    ("devices.create", "devices", "Create Device", "POST /", ["superadmin", "hr", "admin"]),
    ("devices.update", "devices", "Update Device", "PUT /<id>", ["superadmin", "hr", "admin"]),
    ("devices.assign", "devices", "Assign Device", "POST /<id>/assign", ["superadmin", "hr", "admin"]),
    ("devices.return", "devices", "Return Device", "POST /<id>/return", ["superadmin", "hr", "admin"]),
    ("devices.upload_image", "devices", "Upload Device Image", "POST /<id>/upload-image", ["superadmin", "hr", "admin"]),
    ("devices.history", "devices", "View Device History", "GET /<id>/history", ["superadmin", "hr", "admin"]),
    ("devices.delete", "devices", "Delete Device", "DELETE /<id>", ["superadmin", "hr", "admin"]),
    ("devices.inventory_dashboard", "devices", "View Inventory Dashboard", "GET /inventory", ["superadmin", "hr", "admin"]),
    ("devices.low_stock_alerts", "devices", "View Low Stock Alerts", "GET /inventory/low-stock", ["superadmin", "hr", "admin"]),
    ("devices.stock_reconciliation", "devices", "Reconcile Stock", "GET /inventory/reconcile", ["superadmin", "hr", "admin"]),
    ("devices.catalog_view", "devices", "View Device Catalog", "GET /catalog", ["superadmin", "hr", "admin"]),
    ("devices.catalog_create", "devices", "Create Catalog Entry", "POST /catalog", ["superadmin", "hr", "admin"]),
    ("devices.catalog_update", "devices", "Update Catalog Entry", "PUT /catalog/<id>", ["superadmin", "hr", "admin"]),
    ("devices.catalog_stock", "devices", "View Catalog Stock", "GET /catalog/<id>/stock", ["superadmin", "hr", "admin"]),
    ("devices.change_status", "devices", "Change Device Status", "PATCH /<id>/status", ["superadmin", "hr", "admin"]),
    ("devices.lifecycle", "devices", "View Device Lifecycle", "GET /<id>/lifecycle", ["superadmin", "hr", "admin"]),
    ("documents.employee_status", "documents", "View Employee Document Status", "GET /<emp_id>/status", ["superadmin", "hr", "admin"]),
    ("documents.list_pending", "documents", "List Pending Documents", "GET /pending-review", ["superadmin", "hr", "admin"]),
    ("documents.verify", "documents", "Verify Document", "PUT /verify/<id>", ["superadmin", "hr", "admin"]),
    ("documents.reject", "documents", "Reject Document", "PUT /reject/<id>", ["superadmin", "hr", "admin"]),
    ("employees.allocation_config", "employees", "Update Allocation Config", "PATCH /<id>/allocation-config", ["superadmin", "hr", "manager", "admin"]),
    ("employees.create", "employees", "Create Employee", "POST /", ["superadmin", "hr", "admin"]),
    ("employees.update", "employees", "Update Employee", "PUT /<id>", ["superadmin", "hr", "admin"]),
    ("employees.delete", "employees", "Delete Employee", "DELETE /<id>", ["superadmin", "hr", "admin"]),
    ("helpdesk.stats", "helpdesk", "View Helpdesk Stats", "GET /stats", ["superadmin", "hr", "admin"]),
    ("helpdesk.history", "helpdesk", "View Ticket History", "GET /<id>/history", ["superadmin", "hr", "admin"]),
    ("helpdesk.update_status", "helpdesk", "Update Ticket Status", "PATCH /<id>/status", ["superadmin", "hr", "admin"]),
    ("helpdesk.assign", "helpdesk", "Assign Ticket", "PATCH /<id>/assign", ["superadmin", "hr", "admin"]),
    ("helpdesk.change_priority", "helpdesk", "Change Ticket Priority", "PATCH /<id>/priority", ["superadmin", "hr", "admin"]),
    ("helpdesk.delete", "helpdesk", "Delete Ticket", "DELETE /<id>", ["superadmin", "hr", "admin"]),
    ("holidays.create", "holidays", "Create Holiday", "POST /", ["superadmin", "hr", "admin"]),
    ("leave.view_all_balances", "leave", "View All Leave Balances", "GET /balance/all", ["superadmin", "hr", "manager", "admin"]),
    ("leave.currently_on_leave", "leave", "View Currently On Leave", "GET /currently-on-leave", ["superadmin", "hr", "manager", "admin"]),
    ("leave.analytics", "leave", "View Leave Analytics", "GET /analytics", ["superadmin", "hr", "manager", "admin"]),
    ("projects.create", "projects", "Create Project", "POST /", ["superadmin", "hr", "admin"]),
    ("projects.update", "projects", "Update Project", "PUT /<id>", ["superadmin", "hr", "manager", "admin"]),
    ("projects.assign_employee", "projects", "Assign Employee to Project", "POST /assign", ["superadmin", "hr", "manager", "admin"]),
    ("projects.remove_assignment", "projects", "Remove Employee Assignment", "DELETE /assign", ["superadmin", "hr", "manager", "admin"]),
    ("projects.update_assignment", "projects", "Update Employee Assignment", "PUT /assign", ["superadmin", "hr", "manager", "admin"]),
    ("projects.delete", "projects", "Delete Project", "DELETE /<id>", ["superadmin", "hr", "admin"]),
    ("reimbursements.stats", "reimbursements", "View Reimbursement Stats", "GET /stats", ["superadmin", "hr", "manager", "admin"]),
    ("reimbursements.approve", "reimbursements", "Approve Reimbursement", "PATCH /<id>/approve", ["superadmin", "hr", "manager", "admin"]),
    ("reimbursements.reject", "reimbursements", "Reject Reimbursement", "PATCH /<id>/reject", ["superadmin", "hr", "manager", "admin"]),
    ("reimbursements.mark_paid", "reimbursements", "Mark Reimbursement Paid", "PATCH /<id>/pay", ["superadmin", "hr", "manager", "admin"]),
    ("reimbursements.history", "reimbursements", "View Reimbursement History", "GET /<id>/history", ["superadmin", "hr", "manager", "admin"]),
    ("reports.resource_utilization", "reports", "View Resource Utilization", "GET /resource/utilization", ["superadmin", "hr", "manager", "admin"]),
    ("reports.billing_ratio", "reports", "View Billing Ratio", "GET /resource/billing-ratio", ["superadmin", "hr", "manager", "admin"]),
    ("reports.over_allocated", "reports", "View Over-Allocated", "GET /resource/over-allocated", ["superadmin", "hr", "manager", "admin"]),
    ("reports.project_billing", "reports", "View Project Billing", "GET /resource/project-billing", ["superadmin", "hr", "manager", "admin"]),
    ("policies.create", "policies", "Create Policy", "POST /policies", ["superadmin", "hr", "admin"]),
    ("policies.update", "policies", "Update Policy", "PUT /policies/<id>", ["superadmin", "hr", "admin"]),
    ("policies.delete", "policies", "Delete Policy", "DELETE /policies/<id>", ["superadmin", "hr", "admin"]),
    ("team_members.create", "team_members", "Create Team Member", "POST /", ["superadmin", "hr", "admin"]),
    ("team_members.update", "team_members", "Update Team Member", "PATCH /<id>", ["superadmin", "hr", "admin"]),
    ("team_members.delete", "team_members", "Delete Team Member", "DELETE /<id>", ["superadmin", "admin"]),
    ("team_members.allocation_config", "team_members", "Update Team Member Allocation Config", "PATCH /<id>/allocation-config", ["superadmin", "hr", "manager", "admin"]),
]

CONFIGURABLE_ROLES = ['superadmin', 'admin', 'hr', 'manager', 'employee', 'team_member', 'onboarding_candidate']

def run_migration():
    try:
        with Transaction() as cursor:
            # 1. Run the table creation SQL
            logger.info("Creating permission tables...")
            sql_path = os.path.join(os.path.dirname(__file__), '025_permission_management.sql')
            with open(sql_path, 'r') as f:
                sql = f.read()
            for statement in sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    cursor.execute(statement)
            
            # 2. Seed Permissions and Role_Permissions
            logger.info("Seeding permission catalog and role grants...")
            for p_key, module, label, route_ref, granted_roles in SEED_PERMISSIONS:
                # Insert permission
                cursor.execute("""
                    INSERT IGNORE INTO permissions (permission_key, module, label, route_reference)
                    VALUES (%s, %s, %s, %s)
                """, (p_key, module, label, route_ref))
                
                cursor.execute("SELECT id FROM permissions WHERE permission_key = %s", (p_key,))
                perm_id = cursor.fetchone()['id']
                
                # Insert role_permissions for all configurable roles
                for role in CONFIGURABLE_ROLES:
                    is_granted = role in granted_roles
                    cursor.execute("""
                        INSERT IGNORE INTO role_permissions (role, permission_id, is_granted)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE is_granted = VALUES(is_granted)
                    """, (role, perm_id, is_granted))

            logger.info("Migration 025 complete.")
            return True
    except Exception as e:
        logger.error(f"Migration 025 failed: {e}")
        return False

if __name__ == '__main__':
    run_migration()
