"""
Seed initial data — roles, admin user, and demo users.
Only runs if the roles table is empty (first-time setup).
"""
from app.database.session import SessionLocal
from app.auth.models import Role, User
from app.auth.service import hash_password


def seed_initial_data():
    """
    Seed the database with default roles and demo users.
    Skips if data already exists.
    """
    db = SessionLocal()
    try:
        # Check if roles already seeded
        existing_roles = db.query(Role).count()
        if existing_roles > 0:
            print("   -> Data already seeded, skipping.")
            return

        # ── Seed Roles ────────────────────────────────────────
        roles = [
            Role(
                name="employee",
                clearance_level=1,
                description="Standard employee access. Can view general company documents.",
            ),
            Role(
                name="manager",
                clearance_level=2,
                description="Manager access. Can view general + confidential documents and upload files.",
            ),
            Role(
                name="admin",
                clearance_level=3,
                description="Full administrator access. Can view all documents and manage users.",
            ),
        ]
        db.add_all(roles)
        db.commit()
        print("   -> Roles seeded: employee, manager, admin")

        # Refresh to get IDs
        for role in roles:
            db.refresh(role)

        role_map = {r.name: r.id for r in roles}

        # ── Seed Demo Users ───────────────────────────────────
        demo_users = [
            User(
                username="admin",
                email="admin@company.com",
                hashed_password=hash_password("admin123"),
                role_id=role_map["admin"],
            ),
            User(
                username="manager1",
                email="manager1@company.com",
                hashed_password=hash_password("manager123"),
                role_id=role_map["manager"],
            ),
            User(
                username="employee1",
                email="employee1@company.com",
                hashed_password=hash_password("employee123"),
                role_id=role_map["employee"],
            ),
        ]
        db.add_all(demo_users)
        db.commit()
        print("   -> Demo users seeded: admin, manager1, employee1")

    except Exception as e:
        db.rollback()
        print(f"   -> Seed error: {e}")
    finally:
        db.close()
