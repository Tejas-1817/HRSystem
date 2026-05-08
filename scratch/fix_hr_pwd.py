from app.models.database import execute_query
from werkzeug.security import generate_password_hash

hashed = generate_password_hash("Welcome@123")
execute_query("UPDATE users SET password=%s WHERE username='riya@gmail.com'", (hashed,), commit=True)
print("Updated riya@gmail.com password to Welcome@123")
