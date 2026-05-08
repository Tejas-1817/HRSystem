from app.models.database import execute_query
from werkzeug.security import generate_password_hash

hashed_password = generate_password_hash("Saurabh@123")
execute_query("UPDATE users SET password=%s WHERE username='saurabh@gmail.com'", (hashed_password,), commit=True)
print("✅ Password for saurabh@gmail.com updated to: Saurabh@123")

hashed_password_raj = generate_password_hash("Raj@123")
execute_query("UPDATE users SET password=%s WHERE username='raj@gmail.com'", (hashed_password_raj,), commit=True)
print("✅ Password for raj@gmail.com updated to: Raj@123")
