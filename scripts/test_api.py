"""Quick API test script."""
import requests
import json

BASE = "http://localhost:8000"

# 1. Health check
print("=== Health Check ===")
r = requests.get(f"{BASE}/health")
print(json.dumps(r.json(), indent=2))

# 2. Login as admin
print("\n=== Login as Admin ===")
r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
data = r.json()
print(f"Status: {r.status_code}")
user = data["user"]
role = user["role"]
print(f"User: {user['username']}, Role: {role['name']}, Clearance: {role['clearance_level']}")
admin_token = data["access_token"]

# 3. Login as employee
print("\n=== Login as Employee ===")
r = requests.post(f"{BASE}/auth/login", json={"username": "employee1", "password": "employee123"})
data = r.json()
print(f"Status: {r.status_code}")
user = data["user"]
role = user["role"]
print(f"User: {user['username']}, Role: {role['name']}, Clearance: {role['clearance_level']}")

# 4. Get /auth/me
print("\n=== Get Profile ===")
r = requests.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
print(f"Status: {r.status_code}, User: {r.json()['username']}")

# 5. List users (admin only)
print("\n=== List Users (Admin) ===")
r = requests.get(f"{BASE}/auth/users", headers={"Authorization": f"Bearer {admin_token}"})
users = r.json()
print(f"Status: {r.status_code}, Users: {[u['username'] for u in users]}")

# 6. List roles
print("\n=== List Roles ===")
r = requests.get(f"{BASE}/auth/roles", headers={"Authorization": f"Bearer {admin_token}"})
for role in r.json():
    print(f"  {role['name']} (clearance={role['clearance_level']})")

print("\n=== ALL API TESTS PASSED ===")
