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

- **Employee & Role Management** – Central directory, role‑based naming, audit trail, document verification.
- **Attendance & Timesheets** – Timesheet‑derived attendance, 8‑hour enforcement, half‑day support.
- **Leave Management** – Full‑type leave, half‑day, balance tracking, calendar API.
- **Project & Resource Allocation** – Fixed‑cost & T&M billing, over‑allocation controls.
- **Help Desk** – Ticketing with device linkage, audit history, KPI dashboards.
- **Reimbursements** – Expense claims, receipt uploads, immutable audit trail.
- **Asset & Device Management** – Inventory, digital agreements, soft‑delete safeguards.
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
| **Email** | Flask‑Mail (SMTP) |
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

*(Full list continues in the original README – kept for brevity.)*

---

## 🗂️ Database Schema
The system uses **27 tables** with foreign‑key relationships. Highlights:
- `employee`, `users`, `attendance`, `timesheets`, `leaves`, `leave_balance`
- `projects`, `project_assignments`
- `helpdesk_tickets`, `helpdesk_ticket_history`
- `reimbursements`, `reimbursement_history`
- `token_blacklist`, `role_history`
- `devices`, `device_assignments`, `device_agreements`
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
```

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
