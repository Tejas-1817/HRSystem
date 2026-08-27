from app.models.database import execute_query

holidays = [
    ('Republic Day', '2026-01-26', 'public', 'Public Holiday'),
    ('May Day & Maharashtra Day', '2026-05-01', 'public', 'Public Holiday'),
    ('Bakrid', '2026-05-28', 'public', 'Public Holiday'),
    ('Independence Day', '2026-08-15', 'public', 'Public Holiday'),
    ('Ganesh Chaturthi', '2026-09-14', 'public', 'Public Holiday'),
    ('Gandhi Jayanti', '2026-10-02', 'public', 'Public Holiday'),
    ('Diwali', '2026-11-09', 'public', 'Public Holiday'),
    ('Christmas', '2026-12-25', 'public', 'Public Holiday'),
    ('New Years', '2026-01-01', 'optional', 'Optional Holiday'),
    ('Makara Sankranthi', '2026-01-15', 'optional', 'Optional Holiday'),
    ('Holi', '2026-03-03', 'optional', 'Optional Holiday'),
    ('Ugadi/Gudi Padwa', '2026-03-19', 'optional', 'Optional Holiday'),
    ('Good Friday', '2026-04-03', 'optional', 'Optional Holiday'),
    ('Dasara', '2026-10-20', 'optional', 'Optional Holiday')
]

execute_query("DELETE FROM holidays", commit=True)
for name, date, htype, desc in holidays:
    execute_query(
        "INSERT INTO holidays (name, date, type, description) VALUES (%s, %s, %s, %s)",
        (name, date, htype, desc),
        commit=True
    )

rows = execute_query("SELECT id, name, date, type, description FROM holidays ORDER BY date")
print(f"Successfully updated {len(rows)} holidays in database:")
for r in rows:
    print(f"  {r['date']} | {r['name']:<28} | {r['type']:<10} | {r['description']}")
