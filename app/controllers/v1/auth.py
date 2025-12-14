from flask import request, redirect
from flask_restx import Namespace, Resource, fields
import os

# Declare API namespace
api = Namespace('auth', 'Authentication endpoints for customer identity service')

# Define models/DTOs
registration_dto = api.model("RegistrationRequest", {
    "email": fields.String(required=True, description="Địa chỉ email"),
    "password": fields.String(required=True, description="Mật khẩu (ít nhất 8 ký tự, chứa chữ hoa, chữ thường, số)"),
    "full_name": fields.String(required=True, description="Họ và tên đầy đủ"),
    "address": fields.String(required=True, description="Địa chỉ"),
})

login_dto = api.model("LoginRequest", {
    "email": fields.String(required=True, description="Địa chỉ email đăng ký"),
    "password": fields.String(required=True, description="Mật khẩu"),
})

customer_dto = api.model("Customer", {
    "customer_id": fields.String(description="ID khách hàng"),
    "email": fields.String(description="Địa chỉ email"),
    "full_name": fields.String(description="Họ và tên"),
    "status": fields.String(description="Trạng thái tài khoản"),
})

registration_response_dto = api.model("RegistrationResponse", {
    "status": fields.String(description="Trạng thái: success hoặc error"),
    "customer_id": fields.String(description="ID khách hàng vừa tạo"),
    "message": fields.String(description="Thông báo"),
})

login_response_dto = api.model("LoginResponse", {
    "status": fields.String(description="Trạng thái: success hoặc error"),
    "message": fields.String(description="Thông báo"),
    "access_token": fields.String(description="JWT access token"),
    "token_type": fields.String(description="Loại token (Bearer)"),
    "expires_in": fields.Integer(description="Thời gian hết hạn (giây)"),
    "customer": fields.Nested(customer_dto, description="Thông tin khách hàng"),
})

error_response_dto = api.model("ErrorResponse", {
    "status": fields.String(description="Trạng thái: error"),
    "error_code": fields.String(description="Mã lỗi"),
    "message": fields.String(description="Thông báo lỗi"),
})

jwks_key_dto = api.model("JWKSKey", {
    "kid": fields.String(description="Key ID (UUID)"),
    "kty": fields.String(description="Key type (RSA)"),
    "alg": fields.String(description="Algorithm (RS256)"),
    "use": fields.String(description="Key usage (sig)"),
    "public_key": fields.String(description="Public key in PEM format"),
})


# Dependency injection - will be set by main app
customer_identity_service = None
jwt_service = None
message_queue_service = None
logging_service = None


@api.route('/register')
class Register(Resource):
    @api.doc('register_customer')
    @api.expect(registration_dto)
    @api.response(201, 'Success', registration_response_dto)
    @api.response(400, 'Invalid Input', error_response_dto)
    @api.response(409, 'email Already Exists', error_response_dto)
    def post(self):
        """Register a new customer account (UC-01)"""
        data = request.json
        
        # Validate required fields
        if not all(key in data for key in ["email", "password", "full_name", "address"]):
            return {
                "status": "error",
                "error_code": "INVALID_INPUT",
                "message": "Thông tin đăng ký không hợp lệ"
            }, 400
        
        email = data.get("email")
        password = data.get("password")
        full_name = data.get("full_name")
        address = data.get("address")
        
        success, message, customer_id = customer_identity_service.register_customer(
            email=email,
            password=password,
            full_name=full_name,
            address=address
        )
        
        if success:
            # Publish customer_registered event to S08 Metrics Service
            try:
                event_body = {
                    "event_type": "customer_registered",
                    "params": {
                        "customer_id": customer_id
                    },
                    "id": customer_id  # Use customer_id as event id
                }
                message_queue_service.publish(
                    queue_name=os.getenv("S04_EVENTS_QUEUE", "s04_events_queue"),
                    message=event_body
                )
            except Exception as e:
                logging_service.log_warning(f"Failed to publish customer_registered event: {str(e)}")
            
            return {
                "status": "success",
                "customer_id": customer_id,
                "message": message
            }, 201
        else:
            # Determine error code based on message
            if "đã được đăng ký" in message:
                error_code = "EMAIL_ALREADY_EXISTS"
                status_code = 409
            else:
                error_code = "INVALID_INPUT"
                status_code = 400
            
            return {
                "status": "error",
                "error_code": error_code,
                "message": message
            }, status_code


@api.route('/login')
class Login(Resource):
    @api.doc('login_customer')
    @api.expect(login_dto)
    @api.response(200, 'Success', login_response_dto)
    @api.response(400, 'Missing Credentials', error_response_dto)
    @api.response(401, 'Invalid Credentials', error_response_dto)
    @api.response(403, 'Account Inactive', error_response_dto)
    def post(self):
        """Authenticate customer and receive JWT token (UC-02)"""
        data = request.json
        
        # Validate required fields
        if not data or not data.get("email") or not data.get("password"):
            return {
                "status": "error",
                "error_code": "MISSING_CREDENTIALS",
                "message": "Vui lòng nhập email và mật khẩu"
            }, 400
        
        email = data.get("email")
        password = data.get("password")
        
        success, message, login_data = customer_identity_service.login_customer(
            email=email,
            password=password
        )
        
        if success:
            return {
                "status": "success",
                "message": message,
                **login_data
            }, 200
        else:
            # Determine error code and status based on message
            if "không đúng" in message:
                error_code = "INVALID_CREDENTIALS"
                status_code = 401
            elif "không được kích hoạt" in message or "bị khóa" in message:
                error_code = "ACCOUNT_INACTIVE"
                status_code = 403
            else:
                error_code = "INVALID_CREDENTIALS"
                status_code = 401
            
            return {
                "status": "error",
                "error_code": error_code,
                "message": message
            }, status_code


@api.route('/oauth/login')
class OAuthLogin(Resource):
    @api.doc('oauth_login')
    @api.response(302, 'Redirect to OAuth Provider')
    def get(self):
        """Initiate OAuth login (redirect to Google) (UC-02a)"""
        provider = request.args.get("provider", "google")
        
        if provider != "google":
            return {
                "status": "error",
                "error_code": "UNSUPPORTED_PROVIDER",
                "message": "Chỉ hỗ trợ Google OAuth"
            }, 400
        
        # Build Google OAuth authorization URL
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        scope = "openid email profile"
        
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={scope}"
        )
        
        logging_service.log_info("Initiating Google OAuth login")
        return redirect(auth_url)


@api.route('/oauth/callback')
class OAuthCallback(Resource):
    @api.doc('oauth_callback')
    @api.response(200, 'Success', login_response_dto)
    @api.response(400, 'Invalid OAuth Code', error_response_dto)
    def get(self):
        """Handle OAuth callback from provider (UC-02a)"""
        code = request.args.get("code")
        
        if not code:
            return {
                "status": "error",
                "error_code": "OAUTH_INVALID_CODE",
                "message": "Mã OAuth không hợp lệ"
            }, 400
        
        # Exchange code for user info
        user_info = customer_identity_service.exchange_google_code_for_token(code)
        
        if not user_info:
            return {
                "status": "error",
                "error_code": "OAUTH_INVALID_CODE",
                "message": "Không thể xác thực với Google"
            }, 400
        
        # Login or create account via OAuth
        success, message, login_data = customer_identity_service.oauth_login(
            email=user_info.get("email"),
            full_name=user_info.get("full_name", ""),
            oauth_provider=user_info.get("provider", "google")
        )
        
        if success:
            return {
                "status": "success",
                "message": message,
                **login_data
            }, 200
        else:
            return {
                "status": "error",
                "error_code": "OAUTH_LOGIN_FAILED",
                "message": message
            }, 400


@api.route('/../.well-known/jwks.json')
class JWKS(Resource):
    @api.doc('get_jwks')
    @api.response(200, 'Success', [jwks_key_dto])
    def get(self):
        """Get JWKS (JSON Web Key Set) for JWT verification"""
        jwks = jwt_service.get_jwks()
        return jwks, 200


def init_dependencies(identity_service, jwt_svc, mq_service, log_service):
    """
    Initialize controller dependencies.
    Called from main app during startup.
    """
    global customer_identity_service, jwt_service, message_queue_service, logging_service
    customer_identity_service = identity_service
    jwt_service = jwt_svc
    message_queue_service = mq_service
    logging_service = log_service
