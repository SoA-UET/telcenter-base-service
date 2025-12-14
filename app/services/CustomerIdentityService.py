from ..services.common.BaseCRUDService import BaseCRUDService
from ..collections.customers import CustomersCollection
from .LoggingService import LoggingService
from .JWTService import JWTService
from bson import ObjectId
import bcrypt
import re
from typing import Dict, Optional, Tuple
from pymongo.errors import DuplicateKeyError
import requests
import os

class CustomerIdentityService(BaseCRUDService):
    """
    Service for customer identity management including registration, 
    authentication, and OAuth support.
    """
    
    def __init__(self, customers_collection: CustomersCollection, 
                 logging_service: LoggingService,
                 jwt_service: JWTService):
        # Initialize with the MongoDB collection
        super().__init__(customers_collection.get_collection(), enable_timing=True)
        self.customers_collection = customers_collection
        self.logging_service = logging_service
        self.jwt_service = jwt_service
        
        self.logging_service.log_info("CustomerIdentityService initialized")
    
    def validate_email(self, email: str) -> bool:
        """
        Validate email format.
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def validate_password(self, password: str) -> bool:
        """
        Validate password strength.
        Requirements: At least 8 characters, contains uppercase, lowercase, and digit
        """
        if len(password) < 8:
            return False
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_digit = bool(re.search(r'\d', password))
        return has_upper and has_lower and has_digit
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def register_customer(self, email: str, password: str, 
                         full_name: str, address: str) -> Tuple[bool, str, Optional[str]]:
        """
        Register a new customer.
        
        Args:
            email: Customer's email address
            password: Plain text password
            full_name: Customer's full name
            address: Customer's address
        
        Returns:
            Tuple of (success, message, customer_id)
        """
        try:
            # Validate email
            if not self.validate_email(email):
                self.logging_service.log_warning(
                    "Invalid email format",
                    {"email": email}
                )
                return False, "Email không hợp lệ", None
            
            # Validate password
            if not self.validate_password(password):
                self.logging_service.log_warning("Weak password provided")
                return False, "Mật khẩu phải có ít nhất 8 ký tự, bao gồm chữ hoa, chữ thường và số", None
            
            # Check if email already exists
            if self.customers_collection.email_exists(email):
                self.logging_service.log_warning(
                    "Email already exists",
                    {"email": email}
                )
                return False, "Email đã được đăng ký", None
            
            # Hash password
            password_hash = self.hash_password(password)
            
            # Create customer
            customer = self.customers_collection.create_customer(
                email=email,
                password_hash=password_hash,
                full_name=full_name,
                address=address
            )
            
            customer_id = str(customer["_id"])
            
            self.logging_service.log_audit(
                "CUSTOMER_REGISTERED",
                customer_id,
                {"email": email, "full_name": full_name}
            )
            
            return True, "Tài khoản được tạo thành công", customer_id
            
        except DuplicateKeyError:
            self.logging_service.log_warning(
                "Duplicate email number",
                {"email": email}
            )
            return False, "Số điện thoại đã được đăng ký", None
        except Exception as e:
            self.logging_service.log_error(
                "Error registering customer",
                {"error": str(e)}
            )
            return False, f"Lỗi hệ thống: {str(e)}", None
    
    def login_customer(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Authenticate customer with email and password.
        
        Args:
            email: Customer's email address
            password: Plain text password
        
        Returns:
            Tuple of (success, message, customer_data_with_token)
        """
        try:
            # Find customer by email
            customer = self.customers_collection.find_by_email(email)
            
            if not customer:
                self.logging_service.log_warning(
                    "Login attempt with non-existent email",
                    {"email": email}
                )
                return False, "Email hoặc mật khẩu không đúng", None
            
            # Check if account is active
            if customer.get("status") != "ACTIVE":
                self.logging_service.log_warning(
                    "Login attempt with inactive account",
                    {"email": email, "customer_id": str(customer["_id"])}
                )
                return False, "Tài khoản chưa được kích hoạt hoặc đã bị khóa", None
            
            # Verify password
            if not self.verify_password(password, customer["password_hash"]):
                self.logging_service.log_warning(
                    "Login attempt with wrong password",
                    {"email": email, "customer_id": str(customer["_id"])}
                )
                return False, "Email hoặc mật khẩu không đúng", None
            
            # Generate JWT token
            customer_id = str(customer["_id"])
            email = customer.get("email")
            access_token = self.jwt_service.sign_token(
                customer_id=customer_id,
                full_name=customer["full_name"],
                email=email
            )
            
            self.logging_service.log_audit(
                "CUSTOMER_LOGIN_SUCCESS",
                customer_id,
                {"email": email}
            )
            
            # Prepare response data
            response_data = {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": self.jwt_service.jwt_expiration_minutes * 60,
                "customer": {
                    "customer_id": customer_id,
                    "email": customer["email"],
                    "full_name": customer["full_name"],
                    "status": customer["status"]
                }
            }
            
            return True, "Đăng nhập thành công", response_data
            
        except Exception as e:
            self.logging_service.log_error(
                "Error during login",
                {"error": str(e), "email": email}
            )
            return False, f"Lỗi hệ thống: {str(e)}", None
    
    def oauth_login(self, email: str, full_name: str, oauth_provider: str = "google") -> Tuple[bool, str, Optional[Dict]]:
        """
        Handle OAuth login. Creates account if it doesn't exist.
        
        Args:
            email: User's email from OAuth provider
            full_name: User's full name from OAuth provider
            oauth_provider: OAuth provider name (e.g., "google")
        
        Returns:
            Tuple of (success, message, customer_data_with_token)
        """
        try:
            # Try to find existing customer by email
            customer = self.customers_collection.find_by_email(email)
            
            if not customer:
                # Create new customer for OAuth user
                customer = self.customers_collection.create_customer(
                    email=email,
                    password_hash="",  # No password for OAuth users
                    full_name=full_name,
                    address="",  # Empty address for OAuth users
                    status="ACTIVE"
                )
                
                customer_id = str(customer["_id"])
                
                self.logging_service.log_audit(
                    "CUSTOMER_OAUTH_REGISTERED",
                    customer_id,
                    {"email": email, "provider": oauth_provider}
                )
            else:
                customer_id = str(customer["_id"])
                
                self.logging_service.log_audit(
                    "CUSTOMER_OAUTH_LOGIN",
                    customer_id,
                    {"email": email, "provider": oauth_provider}
                )
            
            # Generate JWT token
            access_token = self.jwt_service.sign_token(
                customer_id=customer_id,
                full_name=customer.get("full_name", full_name),
                email=email
            )
            
            # Prepare response data
            response_data = {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": self.jwt_service.jwt_expiration_minutes * 60,
                "customer": {
                    "customer_id": customer_id,
                    "email": email,
                    "full_name": customer.get("full_name", full_name),
                    "status": customer.get("status", "ACTIVE")
                }
            }
            
            return True, "Đăng nhập OAuth thành công", response_data
            
        except Exception as e:
            self.logging_service.log_error(
                "Error during OAuth login",
                {"error": str(e), "email": email}
            )
            return False, f"Lỗi hệ thống: {str(e)}", None
    
    def exchange_google_code_for_token(self, code: str) -> Optional[Dict]:
        """
        Exchange Google OAuth authorization code for access token.
        
        Args:
            code: Authorization code from Google
        
        Returns:
            User info dict with email and name, or None on error
        """
        try:
            # Get Google OAuth credentials from environment
            client_id = os.getenv("GOOGLE_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
            redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
            
            # Exchange code for token
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
            
            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()
            token_json = token_response.json()
            
            access_token = token_json.get("access_token")
            
            # Get user info
            userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            userinfo_response = requests.get(userinfo_url, headers=headers)
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()
            
            return {
                "email": userinfo.get("email"),
                "full_name": userinfo.get("name", ""),
                "provider": "google"
            }
            
        except Exception as e:
            self.logging_service.log_error(
                "Error exchanging Google OAuth code",
                {"error": str(e)}
            )
            return None
    
    def get_customers_count(self) -> int:
        """
        Get total count of customers in the database.
        Used for A04b Method API.
        
        Returns:
            Total number of customers
        """
        try:
            count = self.customers_collection.count_customers()
            self.logging_service.log_info(f"Retrieved customers count: {count}")
            return count
        except Exception as e:
            self.logging_service.log_error(
                "Error getting customers count",
                {"error": str(e)}
            )
            raise
