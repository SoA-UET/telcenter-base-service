"""
Customer Identity Service - S04
Handles customer authentication and registration
"""

from pymongo.collection import Collection
from datetime import datetime, timedelta
import bcrypt
import jwt
import os
import re
from typing import Optional
import requests
from .AuditLoggerService import AuditLogger


class CustomerIdentityService:
    def __init__(self, collection: Collection, logger: Optional[AuditLogger] = None):
        self.collection = collection
        self.jwt_secret = os.getenv("JWT_SECRET", "default-secret-key-change-in-production")
        self.jwt_expiration = int(os.getenv("JWT_EXPIRATION_SECONDS", "3600"))
        
        # OAuth configuration
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        
        # Audit logger - inject or create new
        self.logger = logger or AuditLogger("CustomerIdentityService")
        
        # Create unique index on email
        self.collection.create_index("email", unique=True)
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _validate_password(self, password: str) -> bool:
        """
        Validate password strength:
        - At least 8 characters
        - Contains uppercase, lowercase, number, and special character
        """
        if len(password) < 8:
            return False
        
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_digit = bool(re.search(r'\d', password))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
        
        return has_upper and has_lower and has_digit and has_special
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def _generate_jwt_token(self, customer_id: str, email: str) -> str:
        """Generate JWT access token"""
        payload = {
            'customer_id': customer_id,
            'email': email,
            'exp': datetime.utcnow() + timedelta(seconds=self.jwt_expiration),
            'iat': datetime.utcnow()
        }
        token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
        return token
    
    def register_customer(self, email: str, password: str, full_name: str, address: str) -> dict:
        """
        Register a new customer
        Returns: {"customer_id": str, "message": str}
        Raises: ValueError with appropriate error code
        """
        # Validate email format
        if not self._validate_email(email):
            self.logger.log_validation_error("REGISTER", "INVALID_EMAIL", email)
            raise ValueError("INVALID_INPUT:Email không hợp lệ")
        
        # Validate password strength
        if not self._validate_password(password):
            self.logger.log_validation_error("REGISTER", "WEAK_PASSWORD", email)
            raise ValueError("INVALID_INPUT:Mật khẩu phải có ít nhất 8 ký tự, bao gồm chữ hoa, chữ thường, số và ký tự đặc biệt")
        
        # Validate required fields
        if not full_name or not full_name.strip():
            self.logger.log_validation_error("REGISTER", "MISSING_FULL_NAME", email)
            raise ValueError("INVALID_INPUT:Họ tên không được để trống")
        
        if not address or not address.strip():
            self.logger.log_validation_error("REGISTER", "MISSING_ADDRESS", email)
            raise ValueError("INVALID_INPUT:Địa chỉ không được để trống")
        
        # Check if email already exists
        existing_customer = self.collection.find_one({"email": email})
        if existing_customer:
            self.logger.log_registration(email, status="failed", error="EMAIL_ALREADY_EXISTS")
            raise ValueError("EMAIL_ALREADY_EXISTS:Email đã được đăng ký")
        
        # Hash password
        password_hash = self._hash_password(password)
        
        # Create customer document
        customer_doc = {
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name.strip(),
            "address": address.strip(),
            "created_at": datetime.now(),
            "status": "ACTIVE"
        }
        
        # Insert into database
        result = self.collection.insert_one(customer_doc)
        customer_id = str(result.inserted_id)
        
        # Log successful registration
        self.logger.log_registration(email, customer_id, status="success")
        
        return {
            "customer_id": customer_id,
            "message": "Tài khoản được tạo thành công"
        }
    
    def login_customer(self, email: str, password: str) -> dict:
        """
        Authenticate customer and generate JWT token
        Returns: {"access_token": str, "token_type": str, "expires_in": int, "customer": dict, "message": str}
        Raises: ValueError with appropriate error code
        """
        # Validate inputs
        if not email or not password:
            self.logger.log_login(email or "unknown", status="failed", error="MISSING_CREDENTIALS")
            raise ValueError("MISSING_CREDENTIALS:Vui lòng nhập email và mật khẩu")
        
        # Find customer by email
        customer = self.collection.find_one({"email": email})
        if not customer:
            self.logger.log_login(email, status="failed", error="INVALID_CREDENTIALS")
            raise ValueError("INVALID_CREDENTIALS:Email hoặc mật khẩu không đúng")
        
        # Verify password
        if not self._verify_password(password, customer['password_hash']):
            self.logger.log_login(email, str(customer['_id']), status="failed", error="INVALID_PASSWORD")
            raise ValueError("INVALID_CREDENTIALS:Email hoặc mật khẩu không đúng")
        
        # Check account status
        if customer.get('status') != 'ACTIVE':
            customer_id = str(customer['_id'])
            self.logger.log_login(email, customer_id, status="failed", error="ACCOUNT_INACTIVE")
            raise ValueError("ACCOUNT_INACTIVE:Tài khoản chưa được kích hoạt hoặc đã bị khóa")
        
        # Generate JWT token
        customer_id = str(customer['_id'])
        access_token = self._generate_jwt_token(customer_id, email)
        
        # Log successful login
        self.logger.log_login(email, customer_id, status="success", login_method="password")
        
        # Prepare response
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": self.jwt_expiration,
            "customer": {
                "customer_id": customer_id,
                "email": customer['email'],
                "full_name": customer['full_name'],
                "status": customer['status']
            },
            "message": "Đăng nhập thành công"
        }
    
    def oauth_login(self, provider: str) -> str:
        """
        Generate OAuth authorization URL
        Returns: Authorization URL to redirect to
        Raises: ValueError if provider not supported
        """
        if provider.lower() != 'google':
            raise ValueError("UNSUPPORTED_PROVIDER:Chỉ hỗ trợ đăng nhập Google")
        
        if not self.google_client_id or not self.google_redirect_uri:
            raise ValueError("OAUTH_NOT_CONFIGURED:OAuth chưa được cấu hình")
        
        # Google OAuth authorization URL
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={self.google_client_id}&"
            f"redirect_uri={self.google_redirect_uri}&"
            f"response_type=code&"
            f"scope=openid%20email%20profile&"
            f"access_type=offline"
        )
        
        return auth_url
    
    def oauth_callback(self, code: str) -> dict:
        """
        Handle OAuth callback and authenticate user
        Returns: Same format as login_customer
        Raises: ValueError with appropriate error code
        """
        if not code:
            raise ValueError("OAUTH_INVALID_CODE:Mã OAuth không hợp lệ")
        
        if not self.google_client_id or not self.google_client_secret or not self.google_redirect_uri:
            raise ValueError("OAUTH_NOT_CONFIGURED:OAuth chưa được cấu hình")
        
        try:
            # Exchange authorization code for access token
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "code": code,
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
                "redirect_uri": self.google_redirect_uri,
                "grant_type": "authorization_code"
            }
            
            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()
            token_json = token_response.json()
            
            access_token = token_json.get('access_token')
            if not access_token:
                raise ValueError("OAUTH_TOKEN_ERROR:Không thể lấy access token")
            
            # Get user info from Google
            userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            userinfo_response = requests.get(userinfo_url, headers=headers)
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()
            
            email = userinfo.get('email')
            name = userinfo.get('name', email)
            
            if not email:
                raise ValueError("OAUTH_NO_EMAIL:Không thể lấy email từ OAuth provider")
            
            # Find or create customer account
            # Use email as a unique identifier for all users
            customer = self.collection.find_one({"email": email})
            
            if not customer:
                # Create new customer account
                customer_doc = {
                    "email": email,
                    "oauth_provider": "google",
                    "password_hash": "",  # No password for OAuth users
                    "full_name": name,
                    "address": "",  # Empty initially
                    "created_at": datetime.now(),
                    "status": "ACTIVE"
                }
                result = self.collection.insert_one(customer_doc)
                customer_id = str(result.inserted_id)
                user_email = email
            else:
                customer_id = str(customer['_id'])
                user_email = customer.get('email', email)
                
                # Check account status
                if customer.get('status') != 'ACTIVE':
                    raise ValueError("ACCOUNT_INACTIVE:Tài khoản chưa được kích hoạt hoặc đã bị khóa")
            
            # Generate JWT token
            jwt_token = self._generate_jwt_token(customer_id, email)
            
            # Log successful OAuth login
            self.logger.log_oauth_login("google", email, customer_id, status="success")
            
            # Prepare response
            return {
                "access_token": jwt_token,
                "token_type": "Bearer",
                "expires_in": self.jwt_expiration,
                "customer": {
                    "customer_id": customer_id,
                    "email": user_email,
                    "full_name": name,
                    "status": "ACTIVE"
                },
                "message": "Đăng nhập OAuth thành công"
            }
            
        except requests.RequestException as e:
            self.logger.log_oauth_login("google", status="failed", error=f"REQUEST_ERROR: {str(e)}")
            raise ValueError(f"OAUTH_REQUEST_ERROR:Lỗi kết nối OAuth: {str(e)}")
        except Exception as e:
            self.logger.log_oauth_login("google", status="failed", error=str(e))
            raise ValueError(f"OAUTH_ERROR:Lỗi OAuth: {str(e)}")
