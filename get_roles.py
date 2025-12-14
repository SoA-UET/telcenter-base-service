"""
Get list of roles with their IDs and permissions
"""
from dotenv import load_dotenv
load_dotenv()

from app.collections import roles_collection
import json

def get_roles():
    roles = list(roles_collection.find())
    
    print("\n=== Available Roles ===\n")
    for role in roles:
        print(f"Role ID: {role['_id']}")
        print(f"Name: {role['name']}")
        print(f"Permissions: {', '.join(role['permissions'])}")
        print("-" * 50)
    
    print("\nCopy one of the Role IDs above to use when creating employees.")

if __name__ == "__main__":
    get_roles()
