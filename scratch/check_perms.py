import sys
sys.path.insert(0, '.')
from app.models.database import execute_query

rows = execute_query("""
    SELECT DISTINCT p.id, p.permission_key, p.module 
    FROM role_permissions rp 
    JOIN permissions p ON rp.permission_id = p.id 
    WHERE rp.role IN ('employee', 'team_member')
""")
print(f"Total permissions for employee/team_member: {len(rows)}")
for r in rows:
    print(f"{r['module']} -> {r['permission_key']}")

soft_rows = execute_query("""
    SELECT id, permission_key, module FROM permissions WHERE module IN ('software', 'devices')
""")
print(f"\nTotal software/devices permissions: {len(soft_rows)}")
for r in soft_rows:
    print(f"{r['module']} -> {r['permission_key']}")
