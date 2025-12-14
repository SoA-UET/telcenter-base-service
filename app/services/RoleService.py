from pymongo.collection import Collection
from ..utils.logger import Logger
from bson import ObjectId

class RoleService:
    """
    Service for managing roles and permissions
    """
    
    def __init__(self, roles_collection: Collection, logger: Logger):
        self.roles_collection = roles_collection
        self.logger = logger
    
    def create_role(self, name: str, permissions: list[str]) -> dict:
        """
        Create a new role
        
        Args:
            name: Role name
            permissions: List of permission strings
            
        Returns:
            Created role document
        """
        # Check if role already exists
        existing = self.roles_collection.find_one({"name": name})
        if existing:
            raise ValueError("Role already exists")
        
        role_doc = {
            "name": name,
            "permissions": permissions
        }
        
        result = self.roles_collection.insert_one(role_doc)
        
        self.logger.audit("role_created", details={"name": name, "role_id": str(result.inserted_id)})
        
        return {
            "_id": result.inserted_id,
            **role_doc
        }
    
    def get_role_by_id(self, role_id: str) -> dict:
        """Get role by ID"""
        role = self.roles_collection.find_one({"_id": ObjectId(role_id)})
        if not role:
            raise ValueError("Role not found")
        return role
    
    def list_roles(self) -> list:
        """List all roles"""
        return list(self.roles_collection.find())
