from pymongo.collection import Collection
from ..utils.logger import Logger
from ..utils.password import hash_password, verify_password
from ..utils.jwt_service import JWTService
from datetime import datetime, timedelta
from bson import ObjectId
import secrets
import string

class AuthService:
    """
    Service for authentication operations
    """
    
    def __init__(
        self, 
        employees_collection: Collection,
        roles_collection: Collection,
        login_attempts_collection: Collection,
        jwt_service: JWTService,
        logger: Logger
    ):
        self.employees_collection = employees_collection
        self.roles_collection = roles_collection
        self.login_attempts_collection = login_attempts_collection
        self.jwt_service = jwt_service
        self.logger = logger
        
        self.max_login_attempts = 5
        self.lockout_duration_minutes = 30
    
    def _is_account_locked(self, email: str) -> bool:
        """Check if account is locked due to failed login attempts"""
        attempt = self.login_attempts_collection.find_one({"email": email})
        
        if not attempt:
            return False
        
        if attempt["count"] >= self.max_login_attempts:
            # Check if lockout period has expired
            if datetime.now() < attempt["expires_at"]:
                return True
            else:
                # Lockout period expired, reset counter
                self.login_attempts_collection.delete_one({"email": email})
                return False
        
        return False
    
    def _record_failed_login(self, email: str):
        """Record a failed login attempt"""
        attempt = self.login_attempts_collection.find_one({"email": email})
        
        if not attempt:
            # First failed attempt
            self.login_attempts_collection.insert_one({
                "email": email,
                "count": 1,
                "expires_at": datetime.now() + timedelta(minutes=self.lockout_duration_minutes)
            })
        else:
            # Increment counter
            new_count = attempt["count"] + 1
            self.login_attempts_collection.update_one(
                {"email": email},
                {
                    "$set": {
                        "count": new_count,
                        "expires_at": datetime.now() + timedelta(minutes=self.lockout_duration_minutes)
                    }
                }
            )
    
    def _clear_failed_login(self, email: str):
        """Clear failed login attempts after successful login"""
        self.login_attempts_collection.delete_one({"email": email})
    
    def login(self, email: str, password: str) -> dict:
        """
        Authenticate employee and return access token
        
        Args:
            email: Employee email (used as username)
            password: Employee password
            
        Returns:
            Dictionary containing access token and user info
            
        Raises:
            ValueError: If credentials are invalid or account is locked
        """
        # Check if account is locked
        if self._is_account_locked(email):
            self.logger.audit("login_failed", details={"email": email, "reason": "account_locked"})
            raise ValueError("ACCOUNT_LOCKED_OR_INACTIVE")
        
        # Find employee by email
        employee = self.employees_collection.find_one({"email": email})
        
        if not employee:
            self._record_failed_login(email)
            self.logger.audit("login_failed", details={"email": email, "reason": "employee_not_found"})
            raise ValueError("INVALID_CREDENTIALS")
        
        # Verify password
        if not verify_password(password, employee["password_hash"]):
            self._record_failed_login(email)
            self.logger.audit("login_failed", user_id=str(employee["_id"]), details={"reason": "wrong_password"})
            raise ValueError("INVALID_CREDENTIALS")
        
        # Check if account is active (if status field exists)
        if "status" in employee and employee["status"] != "ACTIVE":
            self.logger.audit("login_failed", user_id=str(employee["_id"]), details={"reason": "account_inactive"})
            raise ValueError("ACCOUNT_LOCKED_OR_INACTIVE")
        
        # Get role and permissions
        role = self.roles_collection.find_one({"_id": employee["role_id"]})
        
        if not role:
            self.logger.error("Role not found for employee", employee_id=str(employee["_id"]))
            raise ValueError("INVALID_CREDENTIALS")
        
        # Clear failed login attempts
        self._clear_failed_login(email)
        
        # Create JWT payload
        payload = {
            "sub": str(employee["_id"]),
            "full_name": employee["full_name"],
            "email": employee["email"],
            "permissions": role.get("permissions", [])
        }
        
        # Sign token
        access_token = self.jwt_service.sign_token(payload)
        
        self.logger.audit("login_success", user_id=str(employee["_id"]))
        
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": self.jwt_service.jwt_expiration_minutes * 60,
            "admin": {
                "employee_id": str(employee["_id"]),
                "full_name": employee["full_name"],
                "role": role["name"],
                "status": employee.get("status", "ACTIVE")
            }
        }
    
    def generate_default_password(self) -> str:
        """Generate a random default password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(12))
        return password
