from app.models.database import execute_query

users = execute_query("SELECT id, username, role, employee_name FROM users")
print("Available Users in DB:")
for u in users:
    print(f"- {u['username']} ({u['role']}) -> {u['employee_name']}")
