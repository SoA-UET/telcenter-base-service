import os
import requests
from typing import Optional, Dict, Tuple
from urllib.parse import urlencode
from ..collections.customers import CustomersCollection
from ..utils.crypto import CryptoUtils
from ..utils.validators import Validators
from .JWTService import JWTService
from .LoggingService import LoggingService

class AuthService:
    """
    Authentication service for customer login, registration, and OAuth.
    """
    
    def __init__(self, customers_collection: CustomersCollection, 
                 jwt_service: JWTService, logging_service: LoggingService):
        self.customers_collection = customers_collection
        self.jwt_service = jwt_service
        self.logging_service = logging_service
        
        # OAuth configuration
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    
    def register_customer(self, email: str, password: str, 
                         full_name: str, address: str) -> Tuple[bool, Dict]:
        """
        Register a new customer.
        
        Returns:
            (success, response_data)
        """
        try:
            # Validate input data
            is_valid, error_message = Validators.validate_registration_data(
                email, password, full_name, address
            )
            
            if not is_valid:
                self.logging_service.log_warning(
                    "Registration validation failed",
                    {"email": email, "error": error_message}
                )
                return False, {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": error_message
                }
            
            # Check if email number already exists
            existing_customer = self.customers_collection.find_by_email(email)
            if existing_customer:
                self.logging_service.log_warning(
                    "Registration failed - email number exists",
                    {"email": email}
                )
                return False, {
                    "status": "error",
                    "error_code": "EMAIL_ALREADY_EXISTS",
                    "message": "Số điện thoại đã được đăng ký"
                }
            
            # Hash password
            password_hash = CryptoUtils.hash_password(password)
            
            # Create customer
            customer = self.customers_collection.create_customer(
                email=email,
                password_hash=password_hash,
                full_name=full_name,
                address=address,
                status="ACTIVE"
            )
            
            customer_id = str(customer["_id"])
            
            self.logging_service.log_audit(
                "CUSTOMER_REGISTERED",
                customer_id,
                {"email": email, "full_name": full_name}
            )
            
            return True, {
                "status": "success",
                "customer_id": customer_id,
                "message": "Tài khoản được tạo thành công"
            }
            
        except Exception as e:
            self.logging_service.log_error(
                "Registration error",
                {"error": str(e), "email": email}
            )
            return False, {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "Đã xảy ra lỗi khi đăng ký"
            }
    
    def login_customer(self, email: str, password: str) -> Tuple[bool, Dict]:
        """
        Authenticate a customer and issue JWT token.
        
        Returns:
            (success, response_data)
        """
        try:
            # Check for missing credentials
            if not email or not password:
                return False, {
                    "status": "error",
                    "error_code": "MISSING_CREDENTIALS",
                    "message": "Vui lòng nhập số điện thoại và mật khẩu"
                }
            
            # Find customer
            customer = self.customers_collection.find_by_email(email)
            
            if not customer:
                self.logging_service.log_warning(
                    "Login failed - customer not found",
                    {"email": email}
                )
                return False, {
                    "status": "error",
                    "error_code": "INVALID_CREDENTIALS",
                    "message": "Số điện thoại hoặc mật khẩu không đúng"
                }
            
            # Verify password
            if not CryptoUtils.verify_password(password, customer["password_hash"]):
                self.logging_service.log_audit(
                    "LOGIN_FAILED",
                    str(customer["_id"]),
                    {"reason": "invalid_password", "email": email}
                )
                return False, {
                    "status": "error",
                    "error_code": "INVALID_CREDENTIALS",
                    "message": "Số điện thoại hoặc mật khẩu không đúng"
                }
            
            # Check account status
            if customer.get("status") != "ACTIVE":
                self.logging_service.log_audit(
                    "LOGIN_FAILED",
                    str(customer["_id"]),
                    {"reason": "inactive_account", "email": email}
                )
                return False, {
                    "status": "error",
                    "error_code": "ACCOUNT_INACTIVE",
                    "message": "Tài khoản chưa được kích hoạt hoặc đã bị khóa"
                }
            
            # Generate JWT token
            customer_id = str(customer["_id"])
            email = customer.get("email")
            access_token = self.jwt_service.sign_token(
                customer_id=customer_id,
                full_name=customer["full_name"],
                email=email
            )
            
            self.logging_service.log_audit(
                "LOGIN_SUCCESS",
                customer_id,
                {"email": email}
            )
            
            return True, {
                "status": "success",
                "message": "Đăng nhập thành công",
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
            
        except Exception as e:
            self.logging_service.log_error(
                "Login error",
                {"error": str(e), "email": email}
            )
            return False, {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "Đã xảy ra lỗi khi đăng nhập"
            }
    
    def get_google_oauth_url(self) -> str:
        """
        Generate Google OAuth authorization URL.
        
        Returns:
            Authorization URL for redirecting user
        """
        params = {
            "client_id": self.google_client_id,
            "redirect_uri": self.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline"
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        self.logging_service.log_info("Generated Google OAuth URL")
        return auth_url
    
    def handle_oauth_callback(self, code: str) -> Tuple[bool, Dict]:
        """
        Handle OAuth callback and authenticate user.
        
        Args:
            code: Authorization code from OAuth provider
        
        Returns:
            (success, response_data)
        """
        try:
            # Exchange code for access token
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "code": code,
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
                "redirect_uri": self.google_redirect_uri,
                "grant_type": "authorization_code"
            }
            
            token_response = requests.post(token_url, data=token_data)
            
            if token_response.status_code != 200:
                self.logging_service.log_error(
                    "OAuth token exchange failed",
                    {"status_code": token_response.status_code}
                )
                return False, {
                    "status": "error",
                    "error_code": "OAUTH_INVALID_CODE",
                    "message": "Mã OAuth không hợp lệ"
                }
            
            access_token = token_response.json().get("access_token")
            
            # Fetch user info
            userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            userinfo_response = requests.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if userinfo_response.status_code != 200:
                self.logging_service.log_error("OAuth userinfo fetch failed")
                return False, {
                    "status": "error",
                    "error_code": "OAUTH_USERINFO_ERROR",
                    "message": "Không thể lấy thông tin người dùng"
                }
            
            user_info = userinfo_response.json()
            email = user_info.get("email")
            full_name = user_info.get("name", "")
            
            # Find or create customer
            # For OAuth, we'll use email as a lookup (if customer has email)
            # Otherwise, we need to create a new customer
            # Note: Since email is required, we'll generate a placeholder or require it later
            
            customer = None
            if email:
                # Try to find customer by email
                customer = self.customers_collection.collection.find_one({"email": email})
            
            if not customer:
                # Create new customer with OAuth data
                # Generate placeholder email number (this is a workaround)
                # In production, you might want to redirect to a form to collect email
                import time
                placeholder_email = f"09{str(int(time.time()))[-8:]}"
                
                # Generate random password hash (won't be used for OAuth login)
                import secrets
                random_password = secrets.token_urlsafe(16)
                password_hash = CryptoUtils.hash_password(random_password)
                
                customer = self.customers_collection.create_customer(
                    email=placeholder_email,
                    password_hash=password_hash,
                    full_name=full_name,
                    address="OAuth User",
                    email=email,
                    status="ACTIVE"
                )
                
                self.logging_service.log_audit(
                    "OAUTH_CUSTOMER_CREATED",
                    str(customer["_id"]),
                    {"email": email, "provider": "google"}
                )
            
            # Generate JWT token
            customer_id = str(customer["_id"])
            jwt_token = self.jwt_service.sign_token(
                customer_id=customer_id,
                full_name=customer["full_name"],
                email=email
            )
            
            self.logging_service.log_audit(
                "OAUTH_LOGIN_SUCCESS",
                customer_id,
                {"email": email, "provider": "google"}
            )
            
            return True, {
                "status": "success",
                "message": "Đăng nhập OAuth thành công",
                "access_token": jwt_token,
                "token_type": "Bearer",
                "expires_in": self.jwt_service.jwt_expiration_minutes * 60,
                "customer": {
                    "customer_id": customer_id,
                    "email": customer["email"],
                    "full_name": customer["full_name"],
                    "status": customer["status"]
                }
            }
            
        except Exception as e:
            self.logging_service.log_error(
                "OAuth callback error",
                {"error": str(e)}
            )
            return False, {
                "status": "error",
                "error_code": "OAUTH_ERROR",
                "message": "Đã xảy ra lỗi khi xử lý OAuth"
            }
