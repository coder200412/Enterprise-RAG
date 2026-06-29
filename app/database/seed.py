"""
Seed initial data — roles, admin user, and demo users.
Only runs if the roles table is empty (first-time setup).
"""
from app.database.session import SessionLocal
from app.auth.models import Role, User
from app.auth.service import hash_password


def seed_initial_data() -> bool:
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
            return False

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
        return True

    except Exception as e:
        db.rollback()
        print(f"   -> Seed error: {e}")
        return False
    finally:
        db.close()


def seed_documents():
    """
    Seed the database with a default PDF (iso27001.pdf) if no documents exist.
    Fails gracefully if Ollama is not reachable or ingestion fails.
    """
    import os
    import shutil
    from app.database.session import SessionLocal
    from app.documents.models import Document
    from app.documents.ingestion import process_file
    from app.documents.vectorstore import add_documents
    from app.auth.models import User
    from app.config import settings

    db = SessionLocal()
    try:
        # Check if documents table already has records
        doc_count = db.query(Document).count()
        if doc_count > 0:
            print("   -> Documents already seeded, skipping.")
            return

        # Find the default iso27001.pdf in the project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        pdf_name = "iso27001.pdf"
        src_pdf_path = os.path.join(project_root, pdf_name)

        if not os.path.exists(src_pdf_path):
            print(f"   -> Default document '{pdf_name}' not found at {src_pdf_path}. Skipping document seed.")
            return

        # Make sure the upload dir exists
        os.makedirs(settings.upload_dir, exist_ok=True)
        dest_pdf_path = os.path.join(settings.upload_dir, pdf_name)

        # Copy the file to the upload directory
        if not os.path.exists(dest_pdf_path):
            shutil.copy(src_pdf_path, dest_pdf_path)
            print(f"   -> Copied '{pdf_name}' to upload directory.")

        # Find the admin user to associate with
        admin_user = db.query(User).filter(User.username == "admin").first()
        admin_id = admin_user.id if admin_user else 1

        # Create database record
        doc = Document(
            filename=pdf_name,
            file_type="pdf",
            clearance_level=1,  # Clearance level 1 (Employee) so everyone can see it
            department="general",
            uploaded_by=admin_id,
            status="processing",
            version=1,
            is_active=True,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        print(f"   -> Ingesting '{pdf_name}' for vector search...")
        # Process the file
        chunks = process_file(
            file_path=dest_pdf_path,
            doc_id=doc.id,
            clearance_level=1,
            department="general"
        )
        tags = chunks[0].metadata.get("tags", "") if chunks else ""
        chunk_count = add_documents(chunks)

        # Update document record
        doc.chunk_count = chunk_count
        doc.tags = tags
        doc.status = "ready"
        db.commit()
        print(f"   [OK] '{pdf_name}' seeded successfully with {chunk_count} chunks.")

    except Exception as e:
        db.rollback()
        print(f"   [WARNING] Document seeding failed: {e}")
        print("   This is expected if your local Ollama instance / ngrok tunnel is offline during startup.")
    finally:
        db.close()

