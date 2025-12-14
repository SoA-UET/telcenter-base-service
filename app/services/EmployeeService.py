from pymongo.collection import Collection
from ..services.common.BaseCRUDService import BaseCRUDService
from ..utils.logger import Logger
from ..utils.password import hash_password
from bson import ObjectId
from datetime import datetime

class EmployeeService(BaseCRUDService):
    """
    Service for managing employee accounts
    """
    
    def __init__(
        self,
        employees_collection: Collection,
        roles_collection: Collection,
        logger: Logger
    ):
        super().__init__(employees_collection, enable_timing=False)
        self.roles_collection = roles_collection
        self.logger = logger
    
    def create_employee(self, full_name: str, role_id: str, default_password: str, partner_id: str = None) -> dict:
        """
        Create a new employee account
        
        Args:
            full_name: Employee full name
            role_id: Role ID
            default_password: Default password (will be hashed)
            partner_id: Optional partner ID
            
        Returns:
            Created employee document
            
        Raises:
            ValueError: If role doesn't exist or employee already exists
        """
        # Validate role exists
        try:
            role_obj_id = ObjectId(role_id)
        except Exception:
            raise ValueError("Invalid role ID format")
            
        role = self.roles_collection.find_one({"_id": role_obj_id})
        if not role:
            raise ValueError("Role not found")
        
        # Generate email from full name (simple implementation)
        # In production, this should be provided by admin or generated more carefully
        email = full_name.lower().replace(" ", ".") + "@telcenter.vn"
        
        # Check if employee already exists
        existing = self.collection.find_one({"email": email})
        if existing:
            raise ValueError("EMPLOYEE_ALREADY_EXISTS")
        
        # Hash password
        password_hash = hash_password(default_password)
        
        # Create employee document
        employee_doc = {
            "full_name": full_name,
            "email": email,
            "password_hash": password_hash,
            "role_id": ObjectId(role_id),
            "status": "INACTIVE",
            "created_at": datetime.now()
        }
        
        if partner_id:
            employee_doc["partner_id"] = partner_id
        
        result = self.collection.insert_one(employee_doc)
        
        self.logger.audit("employee_created", user_id=str(result.inserted_id), details={
            "full_name": full_name,
            "email": email,
            "role_id": role_id
        })
        
        return {
            "_id": result.inserted_id,
            **employee_doc
        }
    
    def update_employee(self, employee_id: str, full_name: str = None, role_id: str = None, status: str = None) -> dict:
        """
        Update employee information
        
        Args:
            employee_id: Employee ID
            full_name: New full name (optional)
            role_id: New role ID (optional)
            status: New status (optional)
            
        Returns:
            Updated employee document
        """
        # Build update document
        update_doc = {}
        
        if full_name:
            update_doc["full_name"] = full_name
        
        if role_id:
            # Validate role exists
            try:
                role_obj_id = ObjectId(role_id)
            except Exception:
                raise ValueError("Invalid role ID format")
            role = self.roles_collection.find_one({"_id": role_obj_id})
            if not role:
                raise ValueError("Role not found")
            update_doc["role_id"] = role_obj_id
        
        if status:
            update_doc["status"] = status
        
        if not update_doc:
            raise ValueError("No fields to update")
        
        update_doc["updated_at"] = datetime.now()
        
        # Update employee
        result = self.collection.find_one_and_update(
            {"_id": ObjectId(employee_id)},
            {"$set": update_doc},
            return_document=True
        )
        
        if not result:
            raise ValueError("Employee not found")
        
        self.logger.audit("employee_updated", user_id=employee_id, details=update_doc)
        
        return result
    
    def delete_employee(self, employee_id: str, lock_only: bool = False) -> dict:
        """
        Delete or disable employee account
        
        Args:
            employee_id: Employee ID
            lock_only: If True, only lock the account; if False, disable it
            
        Returns:
            Success message
        """
        if lock_only:
            # Temporarily lock the account
            result = self.collection.find_one_and_update(
                {"_id": ObjectId(employee_id)},
                {"$set": {"status": "LOCKED", "updated_at": datetime.now()}},
                return_document=True
            )
            action = "employee_locked"
        else:
            # Disable the account (soft delete)
            result = self.collection.find_one_and_update(
                {"_id": ObjectId(employee_id)},
                {"$set": {"status": "INACTIVE", "updated_at": datetime.now()}},
                return_document=True
            )
            action = "employee_disabled"
        
        if not result:
            raise ValueError("Employee not found")
        
        self.logger.audit(action, user_id=employee_id)
        
        return {"status": "success", "message": "Tài khoản nhân viên đã bị vô hiệu hóa"}
    
    def list_employees(self) -> list:
        """
        List all employees with their role information
        
        Returns:
            List of employee documents with role names
        """
        employees = list(self.collection.find())
        
        # Enrich with role information
        for employee in employees:
            role = self.roles_collection.find_one({"_id": employee["role_id"]})
            if role:
                employee["role"] = role["name"]
            else:
                employee["role"] = "Unknown"
            
            # Convert ObjectId to string for JSON serialization
            employee["employee_id"] = str(employee["_id"])
            del employee["_id"]
            del employee["password_hash"]  # Don't expose password hash
            del employee["role_id"]  # Already have role name
            
            # Convert datetime objects to ISO format strings
            if "created_at" in employee:
                employee["created_at"] = employee["created_at"].isoformat()
            if "updated_at" in employee:
                employee["updated_at"] = employee["updated_at"].isoformat()
        
        return employees
