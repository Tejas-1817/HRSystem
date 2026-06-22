# ![HRMS Banner](file:///Users/kartikdahale/.gemini/antigravity/brain/b21edc1f-5720-4e8b-aa7c-041603745c34/readme_banner_1778231502175.png)

# 🏢 Human Resource Management System (HRMS)

[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/database-MySQL-orange.svg)](https://www.mysql.com/)
[![Auth](https://img.shields.io/badge/auth-JWT-green.svg)](https://pyjwt.readthedocs.io/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A robust, modular, production‑ready **Human Resource Management System** built for modern SaaS environments. It offers end‑to‑end HR workflows: employee lifecycle, attendance, leave, timesheets, payroll, assets, help‑desk, reimbursements, policies, and more.

---

## ✨ Key Features

- **Team Member & Role Management** – Central directory, role‑based naming, audit trail, document verification (Legacy "Employee" terminology fully supported via compatibility layer).
- **Attendance & Timesheets** – Timesheet‑derived attendance, 8‑hour enforcement, half‑day support.
- **Leave Management** – Full‑type leave, half‑day, balance tracking, calendar API.
- **Project & Resource Allocation** – Fixed‑cost & T&M billing, over‑allocation controls.
- **Help Desk** – Ticketing with device linkage, audit history, KPI dashboards.
- **Reimbursements** – Expense claims, receipt uploads, immutable audit trail.
- **Asset & Device Management** – Inventory, digital agreements, soft‑delete safeguards, hardware specs tracking.
- **Onboarding & Background Verification** – Candidate workflows, document collection, reference checks, and digital declarations.
- **Security & RBAC** – Four‑tier roles, JWT auth, token blacklist, cache‑prevention headers.
- **Notifications & Alerts** – Personal notifications, birthday/holiday alerts.

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.13+, Flask |
| **Database** | MySQL 8.0+ |
| **Auth** | PyJWT (HS256) |
| **Security** | Werkzeug hashing, RBAC, CORS |
| **Email** | smtplib (SMTP) |
| **Exports** | openpyxl (Excel) |
| **Config** | python‑dotenv |
| **API** | RESTful JSON |

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.13+
- MySQL 8.0+ (or 5.7+)
- `git` and `pip`

### 2. Clone & Setup
```bash
git clone https://github.com/yourorg/HRMS.git
cd HRMS
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 3. Environment Variables
Copy the example and generate a strong JWT secret:
```bash
cp .env.example .env
# generate a 256‑bit secret, e.g.:
openssl rand -hex 32
# paste the output as JWT_SECRET value
```
> **Important**: Keep `.env` out of version control.

### 4. Database Setup
```bash
# Create schema
mysql -u $DB_USER -p $DB_NAME < database/schema.sql
# Seed development data
mysql -u $DB_USER -p $DB_NAME < database/seed.sql
```

#### Incremental Migrations (if DB already exists)
```bash
python database/migrations/run_001.py   # Half‑day leave
python database/migrations/run_002.py   # Help Desk
python database/migrations/run_003.py   # Reimbursements
python database/migrations/run_004.py   # Token blacklist
python database/migrations/run_006.py   # Device management + helpdesk device link
python database/migrations/run_009.py   # Timesheet approval workflow
python database/migrations/run_010.py   # Inventory & stock management
python database/migrations/run_011.py   # Leave approval workflow
```

### 5. Run the Server
```bash
python run.py
```
The API will be available at `http://localhost:5001`.

---

## 📊 API Reference (excerpt)
All protected routes require `Authorization: Bearer <token>`.

### Authentication (`/auth`)
| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | `/auth/login` | Public | Obtain JWT |
| POST | `/auth/register` | HR | Register user |
| POST | `/auth/change-password` | All | Change password |
| GET | `/auth/profile` | All | Current user profile |
| POST | `/auth/logout` | All | Invalidate token |

### Team Members (`/api/v1/team-members`) - *Recommended*
| Method | Endpoint | Role | Description |
|---|---|---|---|
| GET | `/api/v1/team-members` | All | List all team members |
| GET | `/api/v1/team-members/{id}` | All | Get team member details |
| POST | `/api/v1/team-members` | HR | Create new team member |
| PATCH | `/api/v1/team-members/{id}` | HR | Update team member |
| DELETE | `/api/v1/team-members/{id}` | Admin | Soft delete team member |

*Note: Legacy `/api/v1/employees` endpoints are fully supported for backward compatibility.*

*(Full list continues in the original README – kept for brevity.)*

---

## 🗂️ Database Schema
The system uses **32+ tables** with foreign‑key relationships. Highlights:
- `employee`, `users`, `attendance`, `timesheets`, `leaves`, `leave_balance`
- `projects`, `project_assignments`
- `helpdesk_tickets`, `helpdesk_ticket_history`
- `reimbursements`, `reimbursement_history`
- `token_blacklist`, `role_history`
- `devices`, `device_assignments`, `device_agreements`
- `onboarding_joinee`, `onboarding_declaration`, `onboarding_documents`
- …and supporting tables for holidays, notifications, documents, payslips, policies, bank details, audit logs.

---

## 📁 Recent Migrations
| Migration | File | Description |
|---|---|---|
| `001` | `database/migrations/001_half_day_leave.sql` | Adds half‑day leave fields and decimal balance |
| `002` | `database/migrations/002_helpdesk.sql` | Help Desk tables & history |
| `003` | `database/migrations/003_reimbursements.sql` | Reimbursements tables |
| `004` | `database/migrations/004_token_blacklist.sql` | Token blacklist for logout |
| `004b` | `database/migrations/004_role_management.sql` | Role column & audit trail |
| `006` | `database/migrations/006_device_management.sql` | Asset framework & images |
| `007` | `database/migrations/007_device_acceptance.sql` | Regulatory sign‑off ledger |
| `008` | `database/migrations/008_asset_soft_delete.sql` | Soft‑delete safety guards |
| `009` | `database/migrations/009_timesheet_approval_workflow.sql` | Timesheet approval workflow |
| `010` | `database/migrations/010_inventory_management.sql` | Inventory & stock management |
| `011` | `database/migrations/011_leave_approval_workflow.sql` | Leave approval workflow |
| `012` | `database/migrations/012_announcement_management.sql` | Announcement management |
| `013` | `database/migrations/013_fix_name_prefixes.sql` | Role and name prefix removal |
| `014` | `database/migrations/014_timesheet_edit_history.sql` | Timesheet edit history tracking |
| `015` | `database/migrations/015_clean_identity_architecture.sql` | Clean identity architecture |
| `016` | `database/migrations/016_team_member_info_fields.sql` | Additional team member HR fields |
| `017` | `database/migrations/017_onboarding.sql` | Onboarding module & joinee tracking |
| `018` | `database/migrations/018_document_type_enum.sql` | Document type enum extensions |
| `019` | `database/migrations/019_return_asset_enhancements.sql` | Asset return tracking enhancements |
| `020` | `database/migrations/020_device_hardware_specs.sql` | Device hardware specs (RAM, CPU, Storage) |
| `021` | `database/migrations/021_device_asset_id.sql` | Custom asset ID support for devices |
| `022` | `database/migrations/022_asset_ownership_rental.sql` | Asset ownership type & rental vendor details |

Run migrations safely (MySQL‑compatible):
```bash
python database/migrations/run_001.py
python database/migrations/run_002.py
python database/migrations/run_003.py
python database/migrations/run_004.py
python database/migrations/run_006.py
python database/migrations/run_009.py
python database/migrations/run_010.py
python database/migrations/run_011.py
python database/migrations/run_012.py
python database/migrations/run_013.py
python database/migrations/run_014.py
python database/migrations/run_015.py
python database/migrations/run_016.py
python database/migrations/run_017.py
python database/migrations/run_019.py
python database/migrations/run_020.py
python database/migrations/run_021.py
python database/migrations/run_022.py
```

---

## 🔄 Terminology Refactor
The backend has been refactored to use "**Team Member**" instead of "**Employee**" for modern enterprise terminology. This was achieved with **zero breaking changes**. 
- Modern endpoints available at `/api/v1/team-members`
- Legacy `/api/v1/employees` endpoints fully supported.
- Database tables (like `employee`) and schema remain unchanged for stability.
- See [TERMINOLOGY_REFACTOR.md](TERMINOLOGY_REFACTOR.md) and [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for details.

---

## 🤝 Development & Contribution
1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/awesome`.
3. Commit your changes:
   ```bash
   git commit -m "Add awesome feature"
   ```
4. Push and open a Pull Request.
5. Ensure linting (`flake8`) and tests (`pytest`) pass.

---

## 📄 License
MIT © 2026 HRMS Contributors
