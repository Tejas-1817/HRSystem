# Backend Terminology Refactor - Quick Reference Guide

## 📖 TL;DR

✅ **Employee → Team Member** refactor is complete and production-ready.
✅ **Zero breaking changes** - All existing APIs work unchanged.
✅ **New modern endpoints** available at `/api/v1/team-members`.
✅ **Centralized configuration** in `app/config/terminology.py`.

---

## 🚀 Quick Start

### For Backend Developers

#### Using Modern Terminology (Recommended)

```python
# 1. Import terminology management
from app.config.terminology import get_label, get_message

# 2. Use modern service
from app.services.team_member_service import create_team_member_record

# 3. Create with modern terminology
team_member_id, name = create_team_member_record(data, role, cursor)

# 4. Format messages with automatic terminology
error_msg = get_message("not_found")  # "Team Member not found"
success_msg = get_message("created_with_name", name="John")
# → "Team Member John created successfully"
```

#### Using Legacy Terminology (Backward Compatibility)

```python
# Old code continues to work unchanged!
from app.services.employee_service import create_employee_record

employee_name, name = create_employee_record(data, role, cursor)
# Still works - delegates to team_member_service internally
```

---

### For Frontend Developers

#### Option 1: Legacy Endpoint (No Changes)

```javascript
// Your existing code works unchanged
const response = await fetch('/api/v1/employees');
const { employees } = await response.json();
```

#### Option 2: Modern Endpoint (Recommended)

```javascript
// New endpoint with modern terminology
const response = await fetch('/api/v1/team-members');
const { data: team_members } = await response.json();

// Update UI
document.querySelector('.header').textContent = 'Team Members';
```

---

## 📁 File Structure

```
app/
├── config/
│   └── terminology.py              # ✨ Centralized configuration
├── services/
│   ├── team_member_service.py      # ✨ Modern service layer
│   └── employee_service.py         # Legacy wrapper (backward compat)
└── api/routes/
    ├── team_member_routes.py       # ✨ Modern endpoints
    └── employee_routes.py          # Legacy endpoints (updated)

Root:
├── TERMINOLOGY_REFACTOR.md         # 📖 Full documentation
├── IMPLEMENTATION_SUMMARY.md       # 📊 Architecture overview
└── validate_terminology_refactor.py # ✅ Validation script
```

---

## 🔍 Terminology Cheat Sheet

### Labels & Constants

```python
from app.config.terminology import (
    get_label,
    ENTITY,              # "Team Member"
    ENTITY_PLURAL,       # "Team Members"
)

entity = get_label("entity")          # "Team Member"
plural = get_label("entity_plural")   # "Team Members"
```

### Messages (Auto-formatted)

```python
from app.config.terminology import get_message

# Messages automatically substitute {entity} and {entity_plural}
get_message("not_found")
# → "Team Member not found"

get_message("created_with_name", name="John")
# → "Team Member John created successfully"

get_message("permissions_denied", entity_plural=plural)
# → "You do not have permission to manage Team Members"
```

### Audit Events

```python
from app.config.terminology import get_audit_event

event = get_audit_event("entity_created", name="John")
# → "Team Member created: John"

event = get_audit_event("entity_role_changed", old_role="employee", new_role="manager")
# → "Team Member role changed"
```

---

## 🌐 API Endpoints

### Modern Endpoints (Recommended)

```bash
# List all team members
GET    /api/v1/team-members
Response: {"success": true, "data": [...]}

# Get team member
GET    /api/v1/team-members/{id}
Response: {"success": true, "data": {...}}

# Create team member
POST   /api/v1/team-members
Body: {"name": "John", "email": "john@example.com", ...}
Response: {"success": true, "message": "...", "data": {...}}

# Update team member
PATCH  /api/v1/team-members/{id}
Body: {"phone": "1234567890", ...}
Response: {"success": true, "message": "...", "data": {...}}

# Update role (admin only)
PATCH  /api/v1/team-members/{id}/role
Body: {"role": "manager"}
Response: {"success": true, "message": "...", "data": {...}}

# Delete team member (soft delete)
DELETE /api/v1/team-members/{id}
Response: {"success": true, "message": "..."}
```

### Legacy Endpoints (Backward Compatible)

```bash
GET    /api/v1/employees          # Still works
GET    /api/v1/employees/{id}     # Still works
POST   /api/v1/employees          # Still works
PUT    /api/v1/employees/{id}     # Still works
DELETE /api/v1/employees/{id}     # Still works
```

---

## 🛠️ Service Functions

### Team Member Service (Modern)

```python
from app.services.team_member_service import (
    create_team_member_record,      # Create new team member
    update_team_member_role,        # Update role (with cascade)
    get_team_member,                # Fetch by ID
    get_team_member_by_name,        # Fetch by system ID
    list_team_members,              # List with filters
    update_team_member,             # Update profile
    delete_team_member,             # Soft delete
)

# Usage
team_member_id, name = create_team_member_record(data, role, cursor)
team_member = get_team_member(1)
team_members = list_team_members(role_filter="manager")
```

### Employee Service (Legacy - Still Works)

```python
from app.services.employee_service import (
    create_employee_record,         # Still works (delegates to modern)
    update_employee_role,           # Still works (delegates to modern)
)

# These still work for backward compatibility!
employee_name, name = create_employee_record(data, role, cursor)
result = update_employee_role(admin_id, user_id, new_role)
```

---

## 💾 Database (Unchanged)

All database operations remain identical:

```sql
-- Database schema unchanged
SELECT * FROM employee WHERE name = 'T_Kartik';
UPDATE employee SET salary = 80000 WHERE id = 1;
INSERT INTO leave_balance (employee_name, ...) VALUES ('T_Kartik', ...);

-- No migrations needed
-- All existing queries work unchanged
```

---

## ✅ Validation

### Run Validation Script

```bash
python validate_terminology_refactor.py
```

This checks:
- ✅ All imports working
- ✅ Terminology configuration correct
- ✅ Serializers functional
- ✅ API endpoints registered
- ✅ Database schema stable
- ✅ Backward compatibility maintained
- ✅ Error messages use modern terminology

---

## 🔄 Error Messages

### Modern Error Messages

```json
{
  "success": false,
  "error": "Team Member not found"
}

{
  "success": false,
  "error": "Email is required"
}

{
  "success": false,
  "error": "You do not have permission to manage Team Members"
}
```

All use "Team Member" / "Team Members" terminology automatically.

---

## 📋 Response Format

### Modern Response (Recommended)

```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "T_Kartik",
    "original_name": "Kartik",
    "email": "kartik@example.com",
    "salary": 75000.00,
    "date_of_birth": "1995-06-15",
    "birthDate": "1995-06-15",
    "totalLeaves": 20.00,
    "remainingLeaves": 18.50
  }
}
```

### Legacy Response (Still Supported)

```json
{
  "success": true,
  "employee": {
    "id": 1,
    "name": "T_Kartik",
    "email": "kartik@example.com",
    "salary": 75000.00
  }
}
```

Both response formats coexist for backward compatibility.

---

## 🎯 Common Tasks

### Adding New Code

✅ **Always use modern terminology:**

```python
# Good: Uses modern terminology
from app.services.team_member_service import create_team_member_record
from app.config.terminology import get_message

# New code should reference "Team Member"
```

### Maintaining Existing Code

✅ **Legacy code continues to work:**

```python
# Still works - no changes needed
from app.services.employee_service import create_employee_record
```

### Updating Error Messages

✅ **Use terminology management:**

```python
# Good: Error message automatically uses "Team Member"
raise ValueError(get_message("not_found"))

# Bad: Hardcoded "Employee"
raise ValueError("Employee not found")
```

### Adding Audit Events

✅ **Use terminology management:**

```python
# Good: Uses modern terminology
from app.config.terminology import get_audit_event
event = get_audit_event("entity_created", name="John")

# Logs: "Team Member created: John"
```

---

## 🚨 Common Mistakes to Avoid

### ❌ Hardcoded Terminology

```python
# Don't do this
error = "Employee not found"
```

### ✅ Use Configuration

```python
# Do this instead
error = get_message("not_found")  # Auto-formats with "Team Member"
```

---

### ❌ Mixing Old and New Endpoints

```python
# Don't mix in same feature
if legacy_mode:
    fetch('/api/v1/employees')
else:
    fetch('/api/v1/team-members')
```

### ✅ Choose One Consistently

```python
// Pick one and use consistently throughout feature
// Modern (recommended)
fetch('/api/v1/team-members')

// Or legacy (for backward compat only)
fetch('/api/v1/employees')
```

---

### ❌ Modifying Database Schema

```python
-- Don't add "team_member" table
-- Database is unchanged for production stability
```

### ✅ Keep Database Unchanged

```sql
-- Everything stays the same
SELECT * FROM employee;  -- Use this
-- NOT: SELECT * FROM team_member;
```

---

## 📞 When In Doubt

1. **Check terminology config**: `app/config/terminology.py`
2. **Review documentation**: `TERMINOLOGY_REFACTOR.md`
3. **See implementation**: `IMPLEMENTATION_SUMMARY.md`
4. **Run validation**: `python validate_terminology_refactor.py`
5. **Search codebase**: `grep -r "team_member_service" app/`

---

## 🎓 Key Concepts

### Adapter Pattern

Legacy functions delegate to modern implementations:

```python
# Old code calls:
create_employee_record()

# Which internally calls:
create_team_member_record()

# Everything uses consistent business logic!
```

### Centralized Configuration

Single source of truth for terminology:

```python
# Change once in app/config/terminology.py
"entity": "Team Member"

# Automatically updates everywhere:
# - Error messages
# - API responses
# - Audit logs
# - Labels
# - All dependent systems
```

### Dual Endpoint Support

Both old and new endpoints work:

```
/api/v1/employees       ← Legacy
    ↓
/api/v1/team-members    ← Modern

Both return modern terminology by default.
No breaking changes.
```

---

## 📈 Migration Timeline

### Now (Immediate)

- ✅ Use modern `/api/v1/team-members` endpoints for new features
- ✅ All error messages automatically use "Team Member"
- ✅ New service is team_member_service

### Phase 2 (Optional)

- ☐ Gradually migrate frontend to modern endpoints
- ☐ Update UI labels to "Team Member"
- ☐ Deprecate legacy `/api/v1/employees` calls

### Phase 3 (Future)

- ☐ Remove legacy endpoints (after all clients migrated)
- ☐ Consolidate to single service

---

## 🎉 Summary

✅ **What Changed**:
- Modern terminology throughout backend
- Centralized configuration system
- New modern API endpoints
- Updated error messages

✅ **What Stayed Same**:
- Database schema unchanged
- Backward compatible APIs
- All existing code still works
- Zero frontend changes required

✅ **What's Better**:
- Enterprise-grade terminology
- Easy global rebranding
- Consistent messaging
- Production-ready architecture

---

**Last Updated**: 2026-05-14
**Version**: 1.0 - Production Ready
**Status**: ✅ Complete & Deployed

For detailed information, see:
- 📖 `TERMINOLOGY_REFACTOR.md` - Full documentation
- 📊 `IMPLEMENTATION_SUMMARY.md` - Architecture overview
- ✅ `validate_terminology_refactor.py` - Validation tests
