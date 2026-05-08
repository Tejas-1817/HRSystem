# 🏢 Human Resource Management System (HRMS)

[![Python Version](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/database-MySQL-orange.svg)](https://www.mysql.com/)
[![Auth](https://img.shields.io/badge/auth-JWT-green.svg)](https://pyjwt.readthedocs.io/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A robust, modular, and production-ready Human Resource Management System designed for modern SaaS environments. Built with a scalable layered architecture, it empowers HR teams, managers, and employees with automated workflows across attendance, leave, timesheet, payroll, project management, and internal support.

## 🏃 Quick Start (How to Run)

To get the project up and running quickly:

1. **Set up Virtual Environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   Ensure you have a `.env` file (copied from `.env.example`) with valid database credentials.

3. **Run the Application:**
   ```bash
   python run.py
   ```

The server will start, typically on `http://localhost:5001` (or as configured in `.env`).

For full setup details, including database initialization, see the [🚀 Getting Started](#-getting-started) section.

---

## ✨ Key Features

### 👤 Employee & Lifecycle Management
- **Centralized Directory** — Comprehensive employee profiles (contact, salary, DOB, joining date, documents).
- **Role-Based Naming Convention** — Automatic prefixing (`H_`, `M_`, `T_`) based on role with cascading renames across all linked tables.
- **HR Update Access** — HR can update employee details (name, phone, salary, DOB, joining date, status) with full audit logging and cross-table name sync.
- **Document Management** — Secure upload, HR verification, and download workflow for confidential documents (KYC, Education).
- **Birthday & Tenure Alerts** — Today's and upcoming birthday detection with employee photo support.
- **Forgot Password / Reset** — Secure SMTP-based email password reset flow with time-limited tokens.

### ⏰ Workforce & Attendance
- **Timesheet-Derived Attendance** — Daily attendance computed from timesheet entries.
- **8-Hour Enforcement** — Automated tracking of standard hours, overtime, underwork, and half-day detection.
- **Leave Management** — Rule-based leave applications with balance tracking, multi-type support (sick, casual, earned), and approval workflow.
- **Half-Day Leave** — Full support for First Half / Second Half leave with 0.5-day balance deduction, conflict detection, and cross-day validation.
- **Timesheet Hour Cap** — On approved half-day leave days, timesheet submissions are capped at 4 hours server-side.
- **Currently-On-Leave Dashboard** — Real-time view of employees on approved leave today (Manager/HR).
- **Leave Calendar API** — Per-day calendar with `half_day` status, `can_apply_second_half` flag, and `max_hours` metadata.

### 📅 Calendar-Based Timesheet Management
- **Interactive Calendar API** — Monthly calendar returning per-day status for every day of the month.
- **Smart Day Classification** — Each day classified as: `completed`, `missing`, `holiday`, `leave`, `half_day`, `weekend`, or `future`.
- **Date Click Support API** — Fetch one day's entries/status for add/edit modal flows.
- **Missing Entry Detection** — Identifies working days with no timesheet submission (excludes weekends, holidays, approved leaves).
- **Monthly Summary** — Aggregated counts of completed, missing, holiday, leave, weekend, and future days.
- **Full CRUD Operations** — Submit, update, and delete timesheet entries with ownership and status guards.
- **Manager Review Workflow** — Approve or reject entries with comments.
- **Excel Export** — Employees can export their timesheet data as a styled `.xlsx` file.

### 💼 Project & Resource Management
- **Project Classification** — Support for **Fixed Cost** (milestone-based) and **Time & Material** (timesheet-driven) billing models.
- **Resource Allocation** — Assign team members with granular billable/non-billable and allocation percentage settings.
- **Over-Allocation Control** — Controlled over-allocation beyond 100% with a 150% safety hard cap for permitted resources.
- **Automated Employee Status** — Employees auto-transition between `Bench` (0%), `Working` (1–100%), and `Over-Allocated` (>100%).
- **Role-Based Visibility** — HR sees all projects; Managers see their own and assigned projects; Employees see only assigned projects.
- **Auto-Generated IDs** — Professional project IDs (`PROJ-YYYY-XXX`) generated on creation.

### 🎫 Help Desk (Ticket Management)
- **Employee Ticket Creation** — Employees raise support tickets with title, description, category, and priority.
- **Hardware-Linked Tickets** — Tickets can be optionally linked to specific assigned devices for IT support.
- **Ticket Categories** — IT Issue, HR Issue, Payroll, Leave, Others.
- **Priority Levels** — Low, Medium, High, Urgent.
- **Ticket Lifecycle** — Open → In Progress → Resolved → Closed with auto-timestamp on resolution.
- **HR-Only Visibility** — Ticket data is strictly visible only to HR and Admin. Managers are blocked at the API level.
- **Assignment Workflow** — HR assigns tickets to resolvers; status auto-advances to `In Progress` on first assignment.
- **Internal Comments** — Interactive follow-up comments on tickets with optional status updates.
- **Immutable Audit Trail** — Every field change (status, assignment, priority) logged in `helpdesk_ticket_history`.
- **Human-Readable References** — Every ticket gets a `HD-XXXX` style reference for easy communication.
- **Dashboard Stats** — Counts by status, priority, category, and unassigned queue (HR/Admin).

### 🖥️ Asset & Device Management
- **IT Asset Directory** — Track IT hardware (brand, model, serial number, status).
- **Secure Device Assignment** — HR delegates laptops/assets to specific users.
- **Agreement Lifecycle** — Mandatory digital acceptance workflow with legally binding electronic clauses.
- **Data Safeguards** — Blocks hard deletes while resources are bound to employee histories.


### 💸 Reimbursement & Expense Management
- **Expense Claim Submission** — Employees submit claims with title, description, amount, currency, expense date, and category.
- **Expense Categories** — Travel, Food, Accommodation, Office Supplies, Others.
- **Receipt Upload** — Attach jpg/jpeg/png/pdf receipts (max 5 MB); stored securely under `uploads/receipts/`.
- **Claim Lifecycle** — Pending → Approved → Paid (or Rejected) with full timestamp tracking.
- **Approval Workflow** — Manager/HR can approve or reject (with mandatory reason). Employees and assignees are notified automatically.
- **Payment Tracking** — Admin-only action to mark claims as paid with payment date and `processed` status.
- **Human-Readable References** — Every claim gets an `EXP-XXXX` style reference.
- **RBAC-Scoped Listing** — Employees see only their own claims; Manager/HR/Admin see all with rich filtering (status, category, date range, project).
- **Withdrawal** — Employees can withdraw their own `pending` claims; Admin can delete any record.
- **Immutable Audit Trail** — Every state change logged to `reimbursement_history` with actor, old/new values, and notes.
- **Dashboard Stats** — Totals by status, by category, pending-approval queue, and approved-unpaid amounts.

### 🎉 Holiday System
- **Organization-Wide Holidays** — Centralized holiday calendar with types: `public`, `company`, `optional`.
- **Holiday Dashboard** — Today's holidays and upcoming 30-day holiday preview.
- **HR Management** — Add holidays with name, date, type, and description.

### 💰 Financials & Compliance
- **Payroll (Payslips)** — Monthly payslip records with secure file download (employees see only their own).
- **Policy Management** — Central repository for active company policies by category (Core HR, IT, Legal).
- **Bank Details Management** — Employee self-service bank detail submission with HR verification, IFSC validation, masked account numbers, and audit logging.
- **Audit Logging** — Tracks security-sensitive events: password changes, bank verifications, RBAC violations, and employee record updates.

### 🔐 Security & RBAC
- **Strict Role-Based Access Control** — Four-tier RBAC: **Super Admin**, **HR**, **Manager**, **Employee**.
- **JWT Authentication** — Stateless session management with 8-hour token expiry.
- **First-Login Password Change** — Mandatory enforcement with strength validation and reuse prevention.
- **Data Isolation** — Employees only access their own data across all modules.
- **Notification System** — Personal notifications with read/delete support and welcome notifications on registration.
- **Secure Logout** — Server-side session invalidation using a cryptographic token blacklist.
- **Cache Prevention** — Global security headers to prevent browser back-button data leakage.
- **RBAC Violation Logging** — Unauthorized access attempts logged to `audit_logs` with actor, endpoint, and timestamp.

---

## 🛠️ Technology Stack

| Layer              | Technology                                    |
| :----------------- | :-------------------------------------------- |
| **Backend**        | Python 3.13+, Flask                           |
| **Database**       | MySQL 8.0+ (with optimized indexing)          |
| **Authentication** | PyJWT (HS256)                                 |
| **Security**       | Werkzeug password hashing, RBAC, CORS         |
| **Email**          | Flask-Mail (SMTP / Gmail App Password)        |
| **Exports**        | openpyxl (Excel `.xlsx` generation)           |
| **Configuration**  | python-dotenv (.env)                          |
| **API Format**     | RESTful JSON                                  |

---

## 🏗️ Architecture Overview

The system follows a clean, modular **layered architecture**:

```text
Antigravity/
├── app/
│   ├── __init__.py             # Flask app factory + Blueprint registration
│   ├── config.py               # Environment-based configuration
│   ├── api/
│   │   ├── middleware/
│   │   │   └── auth.py         # JWT token_required & role_required decorators
│   │   └── routes/
│   │       ├── auth_routes.py          # Login, register, password reset, user management
│   │       ├── employee_routes.py      # Employee CRUD + HR update endpoint
│   │       ├── attendance_routes.py    # Attendance view derived from timesheets
│   │       ├── timesheet_routes.py     # Timesheets, calendar, missing entries, export
│   │       ├── leave_routes.py         # Leave + half-day applications & calendar
│   │       ├── project_routes.py       # Projects & team assignments
│   │       ├── holiday_routes.py       # Holiday calendar & dashboard
│   │       ├── notification_routes.py  # Notifications (read, delete)
│   │       ├── document_routes.py      # Document upload, verify, download
│   │       ├── report_routes.py        # Payslips, policies & resource reports
│   │       ├── birthday_routes.py      # Birthday alerts
│   │       ├── bank_routes.py          # Bank details CRUD & HR verification
│   │       ├── helpdesk_routes.py      # Help Desk ticket management (9 endpoints)
│   │       ├── reimbursement_routes.py # Expense claim management (10 endpoints)
│   │       └── device_routes.py        # Device procurement & compliance (14 endpoints)
│   ├── models/
│   │   └── database.py         # MySQL connection pool & query helpers
│   ├── services/
│   │   ├── billing_service.py      # Resource utilization, billing ratios & status sync
│   │   ├── device_service.py       # Core inventory, history & soft-delete logic
│   │   ├── employee_service.py     # Atomic employee/user creation logic
│   │   ├── helpdesk_service.py     # Ticket ref generation, RBAC query builder, audit logger
│   │   ├── reimbursement_service.py# Expense ref generation, receipt handler, RBAC query builder
│   │   ├── leave_service.py        # Leave allocation, half-day validation & balance logic
│   │   └── device_agreement_service.py # Compliance signature captures
│   └── utils/
│       ├── helpers.py              # Role naming, cascade rename, project ID generation
│       ├── file_upload.py          # Shared storage pipelines
│       ├── email_service.py        # SMTP wrapper for password resets & notifications
│       ├── excel_utils.py          # Styling and generation logic for XLSX exports
│       ├── logger.py               # Centralized application logging setup
│       └── agreement_template.py   # Corporate indemnity text generators
├── database/
│   ├── schema.sql              # Full database schema (21 tables)
│   ├── seed.sql                # Development seed data
│   └── migrations/
│       ├── 001_half_day_leave.sql  # Half-day leave schema migration
│       ├── run_001.py              # Migration 001 Python runner
│       ├── 002_helpdesk.sql        # Help Desk tables migration
│       ├── run_002.py              # Migration 002 Python runner
│       ├── 003_reimbursements.sql  # Reimbursement tables migration
│       ├── run_003.py              # Migration 003 Python runner
│       ├── 004_token_blacklist.sql  # Token blacklist table migration
│       └── run_004.py              # Migration 004 Python runner
├── uploads/                    # File storage for documents, payslips
├── scratch/                    # Development/test scripts
├── requirements.txt
├── run.py                      # Application entry point
└── .env                        # Environment configuration (not committed)
```

---

## 📊 Database Schema

The system uses **27 tables** with optimized indexing and foreign key relationships:

| Table                       | Purpose                                                      |
| :-------------------------- | :----------------------------------------------------------- |
| `employee`                  | Core employee profiles & utilization status (Working/Bench)  |
| `users`                     | Authentication & RBAC credentials                            |
| `attendance`                | Legacy attendance table (superseded by timesheets)           |
| `daily_work_config`         | Legacy config table (deprecated)                             |
| `timesheets`                | Project-level daily task entries with review flow & export   |
| `leaves`                    | Leave applications with half-day support & approval status   |
| `leave_balance`             | Per-employee leave balance (DECIMAL for 0.5-day support)     |
| `projects`                  | Project master data with billing type (Fixed/T&M)            |
| `project_assignments`       | Resource mapping with billable status & allocation %         |
| `holidays`                  | Organization-wide holiday calendar                           |
| `notifications`             | User notification system                                     |
| `employee_documents`        | Document uploads with verification workflow                  |
| `payslips`                  | Monthly payslip records & file paths                         |
| `policies`                  | Company policies by category                                 |
| `bank_details`              | Employee bank information with HR verification               |
| `audit_logs`                | Security event audit trail (RBAC violations, updates)        |
| `leave_config`              | Configurable default leave quotas per leave type             |
| `helpdesk_tickets`          | Help Desk ticket records with HD-XXXX references             |
| `helpdesk_ticket_history`   | Immutable audit trail for every ticket field change          |
| `reimbursements`            | Expense claim records with EXP-XXXX references & receipt paths |
| `reimbursement_history`     | Immutable audit trail for every expense claim state change   |
| `token_blacklist`          | Cryptographic hashes of invalidated/logged-out JWT tokens     |
| `role_history`             | Immutable audit trail for role changes & security events      |
| `devices`                  | Asset registration logs for organizational tracking           |
| `device_assignments`        | Direct inventory logs connecting hardware mappings            |
| `device_images`            | Visual documentation of hardware assets                       |
| `device_agreements`       | Signature ledgers securing strict acceptable use clauses      |

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.13 or higher
- MySQL Server 5.7+ (or 8.0+ recommended)
- Pip (Python package manager)

### 2. Environment Configuration

Copy `.env.example` to `.env` and fill in your values:

```ini
DB_HOST=localhost
DB_NAME=starterdata
DB_USER=your_username
DB_PASS=your_password
JWT_SECRET=your_super_secret_key_change_in_production
PORT=5001
DEBUG=True
UPLOAD_FOLDER=uploads
DB_POOL_SIZE=10

# Email (for Forgot Password feature)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_16_char_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com
```

### 3. Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

### 4. Database Setup

**Fresh installation** (new database):
```bash
mysql -u your_username -p starterdata < database/schema.sql
mysql -u your_username -p starterdata < database/seed.sql
```

**Existing database** (apply incremental migrations):
```bash
# Migration 001 — Half-Day Leave support
python database/migrations/run_001.py

# Migration 002 — Help Desk tables
python database/migrations/run_002.py

# Migration 003 — Reimbursement tables
python database/migrations/run_003.py

# Migration 004 — Token Blacklist
python database/migrations/run_004.py
```

### 5. Run the Server

```bash
python run.py
```

The API will be available at `http://localhost:5001`.

---

## 🚦 API Reference

All protected routes require `Authorization: Bearer <token>` header.  
The API is organized into **15 Blueprint modules**.

### 🔑 Authentication (`/auth`)

| Method   | Endpoint                      | Role   | Description                                |
| :------- | :---------------------------- | :----- | :----------------------------------------- |
| `POST`   | `/auth/login`                 | Public | Authenticate and receive JWT token         |
| `POST`   | `/auth/register`              | HR     | Register new user with welcome notification|
| `POST`   | `/auth/change-password`       | All    | Change password (enforced on first login)  |
| `GET`    | `/auth/profile`               | All    | Get current user profile                   |
| `GET`    | `/auth/users`                 | HR     | List all users                             |
| `PATCH`  | `/auth/users/<id>/role`       | HR     | Update user role (triggers cascade rename) |
| `POST`   | `/auth/forgot-password`       | Public | Request password reset email               |
| `POST`   | `/auth/reset-password`        | Public | Reset password using emailed token         |
| `POST`   | `/auth/logout`                | All    | Securely logout and invalidate token       |

### 👤 Employees (`/employees`)

| Method   | Endpoint                              | Role | Description                              |
| :------- | :------------------------------------ | :--- | :--------------------------------------- |
| `GET`    | `/employees/`                         | All  | List employees (scoped by role)          |
| `GET`    | `/employees/<id>`                     | All  | Get single employee details              |
| `POST`   | `/employees/`                         | HR   | Add new employee with file upload        |
| `PUT`    | `/employees/<id>`                     | HR   | Update employee details with audit log   |
| `DELETE` | `/employees/<id>`                     | HR   | Remove employee and all linked records   |
| `PATCH`  | `/employees/<id>/allocation-config`   | HR   | Toggle over-allocation permission        |

### ⏰ Attendance (`/attendance`)

| Method | Endpoint        | Role | Description                               |
| :----- | :-------------- | :--- | :---------------------------------------- |
| `GET`  | `/attendance/`  | All  | View timesheet-derived attendance records |

### 📅 Timesheets (`/timesheets`)

| Method   | Endpoint                              | Role       | Description                                         |
| :------- | :------------------------------------ | :--------- | :-------------------------------------------------- |
| `GET`    | `/timesheets/`                        | All        | List timesheet entries (scoped by role)             |
| `POST`   | `/timesheets/`                        | All        | Submit new entry (4-hr cap on half-day leave days)  |
| `PUT`    | `/timesheets/<id>`                    | All        | Update entry (pending/rejected only for employees)  |
| `DELETE` | `/timesheets/<id>`                    | All        | Delete entry (pending/rejected only for employees)  |
| `GET`    | `/timesheets/calendar?year=&month=`   | All        | Monthly calendar with per-day status & `max_hours`  |
| `GET`    | `/timesheets/day?date=YYYY-MM-DD`     | All        | Day detail — entries + status for clicked day       |
| `GET`    | `/timesheets/missing?year=&month=`    | All        | Working days with no timesheet submission           |
| `PATCH`  | `/timesheets/<id>/review`             | Manager/HR | Approve or reject with comments                     |
| `GET`    | `/timesheets/export`                  | All        | Download personal timesheet as Excel (.xlsx)        |

### 🏖️ Leaves (`/leaves`)

| Method   | Endpoint                       | Role       | Description                                          |
| :------- | :----------------------------- | :--------- | :--------------------------------------------------- |
| `GET`    | `/leaves/`                     | All        | List leave applications                              |
| `POST`   | `/leaves/`                     | All        | Apply for leave (full-day or half-day)               |
| `GET`    | `/leaves/balance`              | All        | View leave balances (DECIMAL, supports 0.5)          |
| `GET`    | `/leaves/calendar?year=&month=`| All        | Monthly leave calendar with `half_day` status        |
| `GET`    | `/leaves/currently-on-leave`   | Manager/HR | Employees on leave today                             |
| `PATCH`  | `/leaves/<id>/approve`         | Manager/HR | Approve leave (deducts stored `leave_duration`)      |
| `PATCH`  | `/leaves/<id>/reject`          | Manager/HR | Reject leave (refunds balance if deducted)           |

### 💼 Projects (`/projects`)

| Method   | Endpoint              | Role       | Description                         |
| :------- | :-------------------- | :--------- | :---------------------------------- |
| `GET`    | `/projects/`          | All        | List projects (role-scoped)         |
| `GET`    | `/projects/<id>`      | All        | Project details with team members   |
| `POST`   | `/projects/`          | HR         | Create project (Fixed/T&M type)     |
| `POST`   | `/projects/assign`    | Manager/HR | Assign resource with billable %     |
| `PUT`    | `/projects/assign`    | Manager/HR | Update assignment allocation        |
| `DELETE` | `/projects/assign`    | Manager/HR | Remove resource from project        |

### 🖥️ Devices (`/devices`)

| Method   | Endpoint                        | Role | Description                                           |
| :------- | :------------------------------ | :--- | :---------------------------------------------------- |
| `GET`    | `/devices/`                     | HR   | List global available infrastructure assets           |
| `POST`   | `/devices/`                     | HR   | Import newly acquired workstations securely           |
| `GET`    | `/devices/<id>`                 | All  | Get device details (RBAC: own or HR/Admin)            |
| `POST`   | `/devices/<id>/assign`         | HR   | Creates binding employee handoff relationships        |
| `POST`   | `/devices/<id>/return`         | HR   | Mark device as returned to inventory                  |
| `POST`   | `/devices/<id>/upload-image`   | HR   | Upload visual proof/condition photo for asset         |
| `GET`    | `/devices/my-devices`           | All  | View all assets currently assigned to you             |
| `GET`    | `/devices/<id>/history`         | HR   | Full assignment and repair lifecycle audit trail      |
| `DELETE` | `/devices/<id>`                 | HR   | Soft deletes unused assets (guarded by active links)  |
| `GET`    | `/devices/<id>/agreement`       | All  | Fetch personalized usage agreement (pending acceptance)|
| `POST`   | `/devices/<id>/accept`          | All  | Digitally sign and accept assigned hardware           |
| `POST`   | `/devices/<id>/reject`          | All  | Reject assignment with mandatory reason                |
| `GET`    | `/devices/<id>/acceptance-status`| All  | View current assignment signature status              |

### 💸 Reimbursements (`/reimbursements`)

| Method   | Endpoint                              | Role            | Description                                              |
| :------- | :------------------------------------ | :-------------- | :------------------------------------------------------- |
| `POST`   | `/reimbursements/`                    | All             | Submit claim (JSON or multipart with receipt file)       |
| `GET`    | `/reimbursements/`                    | All (scoped)    | List claims — employees see own; Manager/HR/Admin see all|
| `GET`    | `/reimbursements/<id>`                | All (scoped)    | Single claim with inline audit history                   |
| `GET`    | `/reimbursements/stats`               | Manager/HR/Admin| Totals by status, category, pending queue, unpaid amount |
| `PATCH`  | `/reimbursements/<id>/approve`        | Manager/HR/Admin| Approve claim + notify employee                          |
| `PATCH`  | `/reimbursements/<id>/reject`         | Manager/HR/Admin| Reject with mandatory reason + notify employee           |
| `PATCH`  | `/reimbursements/<id>/pay`            | **Admin only**  | Mark as paid with payment date                           |
| `GET`    | `/reimbursements/<id>/history`        | Manager/HR/Admin| Full immutable audit trail                               |
| `GET`    | `/reimbursements/<id>/receipt`        | All (scoped)    | Download attached receipt file                           |
| `DELETE` | `/reimbursements/<id>`                | Employee (pending own) / Admin | Withdraw or force-delete           |

### 🎫 Help Desk (`/helpdesk`)

| Method   | Endpoint                        | Role           | Description                                           |
| :------- | :------------------------------ | :------------- | :---------------------------------------------------- |
| `POST`   | `/helpdesk/`                    | All            | Raise a new support ticket (linked to device if provided)|
| `GET`    | `/helpdesk/`                    | Emp/HR/Admin   | List tickets (Employees: own only; HR/Admin: all)     |
| `GET`    | `/helpdesk/stats`               | HR/Admin       | Aggregate counts by status, priority, and category    |
| `GET`    | `/helpdesk/<id>`                | Emp/HR/Admin   | Single ticket details with inline audit history       |
| `GET`    | `/helpdesk/<id>/history`        | HR/Admin       | Full immutable audit trail for all field changes      |
| `PATCH`  | `/helpdesk/<id>/status`         | HR/Admin       | Update ticket status (open/in_progress/resolved/closed)|
| `PATCH`  | `/helpdesk/<id>/assign`         | HR/Admin       | Assign resolver and auto-advance status to in_progress|
| `PATCH`  | `/helpdesk/<id>/priority`       | **Admin only** | Update ticket priority (low/medium/high/urgent)       |
| `DELETE` | `/helpdesk/<id>`                | **Admin only** | Close/Soft-delete ticket                              |
| `POST`   | `/helpdesk/<int:id>/comments`   | Emp/HR/Admin   | Add follow-up comment with optional status update     |

> **Note:** Managers are hard-blocked from all ticket endpoints. Every denied attempt is logged in `audit_logs`.

**Filters on `GET /helpdesk/`:**  
`?status=open&priority=high&category=it_issue&search=vpn&assigned_to=H_Saurabh`

**Filters on `GET /reimbursements/`:**  
`?status=pending&category=travel&employee_name=T_Raj&project_id=1&from_date=2026-01-01&to_date=2026-04-30`

### 🎉 Holidays (`/holidays`)

| Method | Endpoint              | Role | Description                          |
| :----- | :-------------------- | :--- | :----------------------------------- |
| `GET`  | `/holidays/`          | All  | List all holidays (filterable by type)|
| `POST` | `/holidays/`          | HR   | Add a new holiday                    |
| `GET`  | `/holidays/dashboard` | All  | Today's + upcoming 30-day holidays   |

### 🔔 Notifications (`/notifications`)

| Method   | Endpoint                    | Role | Description               |
| :------- | :-------------------------- | :--- | :------------------------ |
| `GET`    | `/notifications/`           | All  | List personal notifications|
| `PUT`    | `/notifications/<id>/read`  | All  | Mark as read              |
| `DELETE` | `/notifications/<id>`       | All  | Delete notification       |

### 📄 Documents (`/documents`)

| Method | Endpoint                    | Role | Description                    |
| :----- | :-------------------------- | :--- | :----------------------------- |
| `GET`  | `/documents/my-status`      | All  | View own document statuses     |
| `GET`  | `/documents/pending-review` | HR   | List pending/uploaded documents|
| `PUT`  | `/documents/verify/<id>`    | HR   | Verify an employee document    |
| `GET`  | `/documents/download/<id>`  | All  | Download document file         |

### 💰 Reports (`/reports`)

| Method | Endpoint                              | Role       | Description                        |
| :----- | :------------------------------------ | :--------- | :--------------------------------- |
| `GET`  | `/reports/payslips`                   | All        | List payslips                      |
| `GET`  | `/reports/payslips/download/<id>`     | All        | Download payslip file              |
| `GET`  | `/reports/policies`                   | All        | List active policies               |
| `GET`  | `/reports/resource/utilization`       | Manager/HR | Bench vs Working utilization       |
| `GET`  | `/reports/resource/billing-ratio`     | Manager/HR | Billable vs non-billable stats     |
| `GET`  | `/reports/resource/project-billing`   | Manager/HR | Project revenue estimation         |

### 🎂 Birthdays (`/birthdays`)

| Method | Endpoint              | Role | Description                   |
| :----- | :-------------------- | :--- | :---------------------------- |
| `GET`  | `/birthdays/today`    | All  | Today's birthdays             |
| `GET`  | `/birthdays/upcoming` | All  | Birthdays in the next 7 days  |

### 🏦 Bank Details (`/bank`)

| Method     | Endpoint                        | Role     | Description                          |
| :--------- | :------------------------------ | :------- | :----------------------------------- |
| `POST/PUT` | `/bank/my`                      | Emp/HR   | Add or update own bank details       |
| `GET`      | `/bank/my`                      | All      | View own bank details (masked)       |
| `GET`      | `/bank/`                        | HR       | List all bank details (unmasked)     |
| `GET`      | `/bank/<employee_name>`         | HR       | View specific employee's details     |
| `PATCH`    | `/bank/verify/<employee_name>`  | HR       | Verify bank details (+ audit log)    |
| `GET`      | `/bank/pending`                 | HR       | Employees with unverified details    |
| `DELETE`   | `/bank/<employee_name>`         | HR       | Delete bank record (offboarding)     |

---

## 🔐 RBAC Matrix Summary

| Feature Area        | Employee       | Manager                    | HR               | Admin       |
| :------------------ | :------------- | :------------------------- | :--------------- | :---------- |
| Own profile         | ✅ Read        | ✅ Read                    | ✅ Full          | ✅ Full     |
| Employee directory  | ✅ Own only    | ✅ All (read)              | ✅ Full CRUD     | ✅ Full     |
| Timesheets          | ✅ Own CRUD    | ✅ All + review            | ✅ All + review  | ✅ Full     |
| Leave               | ✅ Own apply   | ✅ All + approve           | ✅ All + approve | ✅ Full     |
| Help Desk tickets   | ✅ Own only    | ❌ **Blocked**             | ✅ All + manage  | ✅ Full     |
| Reimbursements      | ✅ Own + withdraw pending | ✅ All + approve/reject | ✅ All + approve/reject | ✅ Full + pay |
| Projects            | ✅ Assigned    | ✅ Own/assigned            | ✅ All + create  | ✅ Full     |
| Reports             | ✅ Own payslips| ✅ Resource reports        | ✅ All reports   | ✅ Full     |
| Audit logs          | ❌             | ❌                         | ✅               | ✅ Full     |

---

## 🧪 Test Credentials (Development)

| Role     | Username             | Password       | Employee Name |
| :------- | :------------------- | :------------- | :------------ |
| Manager  | `tejas@gmail.com`    | `Tejas@123`    | M_Tejas       |
| Manager  | `priyanka@gmail.com` | `Priyanka@123` | M_Priyanka    |
| HR       | `riya@gmail.com`     | `Riya@123`     | H_Riya        |
| HR       | `saurabh@gmail.com`  | `Saurabh@123`  | H_Saurabh     |
| Employee | `kartik@gmail.com`   | `Kartik@123`   | T_Kartik      |
| Employee | `sneha@gmail.com`    | `Sneha@123`    | T_Sneha       |

> **Note:** All seed users have `password_change_required: TRUE`. After first login, the API enforces a password change before allowing access to other endpoints.

---

## 📦 Recent Migrations

| Migration | File | What It Does |
| :-------- | :--- | :----------- |
| `001` | `database/migrations/001_half_day_leave.sql` | Adds `leave_type_category`, `half_day_period`, `leave_duration` to `leaves`; widens `leave_balance` columns to `DECIMAL(6,2)` |
| `002` | `database/migrations/002_helpdesk.sql` | Creates `helpdesk_tickets` and `helpdesk_ticket_history` tables with indexes and FK constraint |
| `003` | `database/migrations/003_reimbursements.sql` | Creates `reimbursements` and `reimbursement_history` tables with indexes and FK constraint |
| `004` | `database/migrations/004_token_blacklist.sql` | Creates `token_blacklist` table for secure session invalidation |
| `004b`| `database/migrations/004_role_management.sql` | Adds `role` column to `employee` and creates `role_history` audit trail |
| `006` | `database/migrations/006_device_management.sql` | Creates inventory frameworks, images, and helpdesk integration |
| `007` | `database/migrations/007_device_acceptance.sql` | Adds regulatory signoff fields and `device_agreements` ledger |
| `008` | `database/migrations/008_asset_soft_delete.sql` | Ensures secure data destruction safety guards |

Run migrations safely (MySQL-version compatible):
```bash
python database/migrations/run_001.py
python database/migrations/run_002.py
python database/migrations/run_003.py
python database/migrations/run_004.py
```

---

## 🤝 Development & Contribution

1. Fork the project.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

