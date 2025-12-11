from flask import request, redirect
from flask_restx import Namespace, Resource, fields

#######################################
## STEP 1. DECLARE THE API NAMESPACE ##
#######################################

api = Namespace('auth', 'Customer authentication and registration endpoints')

####################################
## STEP 2. DEFINE THE MODELS/DTOs ##
####################################

# Registration request model
registration_dto = api.model("CustomerRegistration", {
    "email": fields.String(required=True, description="Email", example="user@example.com"),
    "password": fields.String(required=True, description="Mật khẩu", example="P@ssw0rd123"),
    "full_name": fields.String(required=True, description="Họ và tên", example="Nguyễn Văn A"),
    "address": fields.String(required=True, description="Địa chỉ", example="TP. Hồ Chí Minh"),
})

# Registration response model
registration_response_dto = api.model("RegistrationResponse", {
    "status": fields.String(description="Trạng thái", example="success"),
    "customer_id": fields.String(description="ID khách hàng", example="10001"),
    "message": fields.String(description="Thông báo", example="Tài khoản được tạo thành công"),
})

# Login request model
login_dto = api.model("CustomerLogin", {
    "email": fields.String(required=True, description="Email", example="user@example.com"),
    "password": fields.String(required=True, description="Mật khẩu", example="P@ssw0rd123"),
})

# Customer info model
customer_info_dto = api.model("CustomerInfo", {
    "customer_id": fields.String(description="ID khách hàng", example="10001"),
    "email": fields.String(description="Email", example="user@example.com"),
    "full_name": fields.String(description="Họ và tên", example="Nguyễn Văn A"),
    "status": fields.String(description="Trạng thái tài khoản", example="ACTIVE"),
})

# Login response model
login_response_dto = api.model("LoginResponse", {
    "status": fields.String(description="Trạng thái", example="success"),
    "message": fields.String(description="Thông báo", example="Đăng nhập thành công"),
    "access_token": fields.String(description="JWT access token", example="<jwt_token>"),
    "token_type": fields.String(description="Loại token", example="Bearer"),
    "expires_in": fields.Integer(description="Thời gian hết hạn (giây)", example=3600),
    "customer": fields.Nested(customer_info_dto, description="Thông tin khách hàng"),
})

# Error response model
error_response_dto = api.model("ErrorResponse", {
    "status": fields.String(description="Trạng thái", example="error"),
    "error_code": fields.String(description="Mã lỗi", example="INVALID_INPUT"),
    "message": fields.String(description="Thông báo lỗi", example="Thông tin đăng ký không hợp lệ"),
})

##################################
## STEP 3. CONNECT THE SERVICES ##
##################################

from ...services import customer_identity_service

###################################
## STEP 4. DEFINE THE CONTROLLER ##
## using the namespace, DTOs and ##
## services we have just defined ##
###################################

@api.route("/register")
class Register(Resource):
    """User registration endpoint"""
    
    @api.doc(description="Đăng ký tài khoản khách hàng mới")
    @api.expect(registration_dto, validate=True)
    @api.response(201, 'Success', registration_response_dto)
    @api.response(400, 'Bad Request - Invalid input', error_response_dto)
    @api.response(409, 'Conflict - Phone already exists', error_response_dto)
    def post(self):
        """Register a new customer account"""
        try:
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')
            full_name = data.get('full_name')
            address = data.get('address')
            
            result = customer_identity_service.register_customer(
                email=email,
                password=password,
                full_name=full_name,
                address=address
            )
            
            return {
                "status": "success",
                **result
            }, 201
            
        except ValueError as e:
            error_msg = str(e)
            if ':' in error_msg:
                error_code, message = error_msg.split(':', 1)
            else:
                error_code = 'INVALID_INPUT'
                message = error_msg
            
            status_code = 409 if error_code == 'EMAIL_ALREADY_EXISTS' else 400
            
            return {
                "status": "error",
                "error_code": error_code,
                "message": message
            }, status_code
        
        except Exception as e:
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "Đã xảy ra lỗi hệ thống"
            }, 500


@api.route("/login")
class Login(Resource):
    """User login endpoint"""
    
    @api.doc(description="Đăng nhập bằng số điện thoại và mật khẩu")
    @api.expect(login_dto, validate=True)
    @api.response(200, 'Success', login_response_dto)
    @api.response(400, 'Bad Request - Missing credentials', error_response_dto)
    @api.response(401, 'Unauthorized - Invalid credentials', error_response_dto)
    @api.response(403, 'Forbidden - Account inactive', error_response_dto)
    def post(self):
        """Authenticate customer and generate JWT token"""
        try:
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')
            
            result = customer_identity_service.login_customer(
                email=email,
                password=password
            )
            
            return {
                "status": "success",
                **result
            }, 200
            
        except ValueError as e:
            error_msg = str(e)
            if ':' in error_msg:
                error_code, message = error_msg.split(':', 1)
            else:
                error_code = 'INVALID_CREDENTIALS'
                message = error_msg
            
            # Determine appropriate HTTP status code
            if error_code == 'MISSING_CREDENTIALS':
                status_code = 400
            elif error_code == 'ACCOUNT_INACTIVE':
                status_code = 403
            else:
                status_code = 401
            
            return {
                "status": "error",
                "error_code": error_code,
                "message": message
            }, status_code
        
        except Exception as e:
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "Đã xảy ra lỗi hệ thống"
            }, 500


@api.route("/oauth/login")
class OAuthLogin(Resource):
    """OAuth login redirect endpoint"""
    
    @api.doc(
        description="Chuyển hướng đến trang đăng nhập OAuth",
        params={
            'provider': 'OAuth provider (currently only "google" is supported)'
        }
    )
    @api.response(302, 'Redirect to OAuth provider')
    @api.response(400, 'Bad Request - Unsupported provider', error_response_dto)
    def get(self):
        """Initiate OAuth login flow"""
        try:
            provider = request.args.get('provider', 'google')
            
            auth_url = customer_identity_service.oauth_login(provider)
            
            return redirect(auth_url)
            
        except ValueError as e:
            error_msg = str(e)
            if ':' in error_msg:
                error_code, message = error_msg.split(':', 1)
            else:
                error_code = 'OAUTH_ERROR'
                message = error_msg
            
            return {
                "status": "error",
                "error_code": error_code,
                "message": message
            }, 400
        
        except Exception as e:
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "Đã xảy ra lỗi hệ thống"
            }, 500


@api.route("/oauth/callback")
class OAuthCallback(Resource):
    """OAuth callback endpoint"""
    
    @api.doc(
        description="Xử lý callback từ OAuth provider",
        params={
            'code': 'Authorization code from OAuth provider',
            'state': 'State parameter (optional)'
        }
    )
    @api.response(200, 'Success', login_response_dto)
    @api.response(400, 'Bad Request - Invalid OAuth code', error_response_dto)
    def get(self):
        """Handle OAuth callback and issue JWT"""
        try:
            code = request.args.get('code')
            
            result = customer_identity_service.oauth_callback(code)
            
            return {
                "status": "success",
                **result
            }, 200
            
        except ValueError as e:
            error_msg = str(e)
            if ':' in error_msg:
                error_code, message = error_msg.split(':', 1)
            else:
                error_code = 'OAUTH_ERROR'
                message = error_msg
            
            return {
                "status": "error",
                "error_code": error_code,
                "message": message
            }, 400
        
        except Exception as e:
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "Đã xảy ra lỗi hệ thống"
            }, 500
