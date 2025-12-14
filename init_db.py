"""
Initialize database with default roles and admin account
"""
from dotenv import load_dotenv
load_dotenv()

from app.collections import employees_collection, roles_collection
from app.utils.password import hash_password
from datetime import datetime

def init_database():
    """
    Initialize database with default data
    """
    print("Initializing database...")
    
    # Check if roles already exist
    existing_roles = list(roles_collection.find())
    if existing_roles:
        print(f"Found {len(existing_roles)} existing roles. Skipping role creation.")
    else:
        # Create default roles
        roles = [
            {
                "name": "ADMIN",
                "permissions": [
                    "employee.read",
                    "employee.write",
                    "employee.delete",
                    "admin.manage"
                ]
            },
            {
                "name": "Tư vấn viên kênh thoại",
                "permissions": [
                    "consult_audio"
                ]
            },
            {
                "name": "Tư vấn viên kênh nhắn tin",
                "permissions": [
                    "consult_text"
                ]
            }
        ]
        
        inserted_roles = []
        for role in roles:
            result = roles_collection.insert_one(role)
            inserted_roles.append({**role, "_id": result.inserted_id})
            print(f"Created role: {role['name']}")
        
        # Find ADMIN role
        admin_role = next(r for r in inserted_roles if r["name"] == "ADMIN")
        
        # Check if admin account already exists
        existing_admin = employees_collection.find_one({"email": "admin_core@telcenter.vn"})
        if existing_admin:
            print("Admin account already exists. Skipping admin creation.")
        else:
            # Create admin account
            admin_password = "Admin@123"
            admin_doc = {
                "full_name": "Admin Core",
                "email": "admin_core@telcenter.vn",
                "password_hash": hash_password(admin_password),
                "role_id": admin_role["_id"],
                "status": "ACTIVE",
                "created_at": datetime.now()
            }
            
            employees_collection.insert_one(admin_doc)
            print(f"Created admin account:")
            print(f"  Email: admin_core@telcenter.vn")
            print(f"  Password: {admin_password}")
    
    print("\nDatabase initialization complete!")
    print("\nYou can now login with:")
    print("  Username: admin_core@telcenter.vn")
    print("  Password: Admin@123")

if __name__ == "__main__":
    init_database()
