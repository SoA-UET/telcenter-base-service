from flask import Blueprint, request, jsonify
from flask_restx import Api, Resource, fields, Namespace
from ...services.AuthService import AuthService
from ...services.EmployeeService import EmployeeService
from ...utils.jwt_service import JWTService
from ...utils.logger import Logger
from functools import wraps
import jwt as pyjwt

def create_auth_required(jwt_service: JWTService, logger: Logger):
    """
    Decorator factory for JWT authentication
    """
    def auth_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            
            if not auth_header:
                logger.warning("Missing Authorization header")
                return jsonify({
                    "status": "error",
                    "error_code": "MISSING_TOKEN",
                    "message": "Token xác thực không được cung cấp"
                }), 401
            
            parts = auth_header.split()
            
            if len(parts) != 2 or parts[0] != 'Bearer':
                logger.warning("Invalid Authorization header format")
                return jsonify({
                    "status": "error",
                    "error_code": "INVALID_TOKEN",
                    "message": "Format token không hợp lệ"
                }), 401
            
            token = parts[1]
            
            try:
                payload = jwt_service.verify_token(token)
                request.user = payload
                return f(*args, **kwargs)
            except pyjwt.ExpiredSignatureError:
                logger.warning("Expired token")
                return jsonify({
                    "status": "error",
                    "error_code": "TOKEN_EXPIRED",
                    "message": "Token đã hết hạn"
                }), 401
            except pyjwt.InvalidTokenError as e:
                logger.warning(f"Invalid token: {str(e)}")
                return jsonify({
                    "status": "error",
                    "error_code": "INVALID_TOKEN",
                    "message": "Token không hợp lệ"
                }), 401
        
        return decorated_function
    return auth_required

def create_role_required(required_permissions: list[str], logger: Logger):
    """
    Decorator factory for permission checking
    """
    def role_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = getattr(request, 'user', None)
            
            if not user:
                logger.warning("No user in request")
                return jsonify({
                    "status": "error",
                    "error_code": "UNAUTHORIZED",
                    "message": "Không có quyền truy cập"
                }), 403
            
            user_permissions = user.get('permissions', [])
            
            # Check if user has all required permissions
            has_all_permissions = all(perm in user_permissions for perm in required_permissions)
            
            if not has_all_permissions:
                logger.warning(f"Insufficient permissions for user {user.get('sub')}")
                return jsonify({
                    "status": "error",
                    "error_code": "FORBIDDEN",
                    "message": "Không có quyền thực hiện thao tác này"
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return role_required

def create_core_auth_blueprint(
    auth_service: AuthService,
    employee_service: EmployeeService,
    jwt_service: JWTService,
    logger: Logger
):
    """
    Create blueprint for Core Authentication and Employee Management API
    """
    blueprint = Blueprint('core_auth', __name__, url_prefix='/api/v1')
    api = Api(
        blueprint,
        version='1.0',
        title='Core Employee Identity Service API',
        description='API for Core employee authentication and management',
        doc='/docs'
    )
    
    # Create namespaces
    auth_ns = Namespace('core-auth', description='Authentication operations')
    employees_ns = Namespace('core-employees', description='Employee management operations')
    
    # Models for Swagger documentation
    login_model = api.model('Login', {
        'username': fields.String(required=True, description='Employee email (username)'),
        'password': fields.String(required=True, description='Employee password')
    })
    
    employee_create_model = api.model('EmployeeCreate', {
        'full_name': fields.String(required=True, description='Employee full name'),
        'role_id': fields.String(required=True, description='Role ID'),
        'partner_id': fields.String(required=False, description='Partner ID (optional)')
    })
    
    employee_update_model = api.model('EmployeeUpdate', {
        'full_name': fields.String(required=False, description='Employee full name'),
        'role_id': fields.String(required=False, description='Role ID'),
        'status': fields.String(required=False, description='Account status')
    })
    
    # Decorators
    auth_required = create_auth_required(jwt_service, logger)
    admin_required = create_role_required(['employee.read', 'employee.write'], logger)
    
    # Auth endpoints
    @auth_ns.route('/login')
    class Login(Resource):
        @auth_ns.expect(login_model)
        def post(self):
            """Admin login"""
            data = request.get_json()
            
            if not data or 'username' not in data or 'password' not in data:
                return {
                    "status": "error",
                    "error_code": "MISSING_FIELDS",
                    "message": "Thiếu tên đăng nhập hoặc mật khẩu"
                }, 400
            
            try:
                result = auth_service.login(data['username'], data['password'])
                
                return {
                    "status": "success",
                    "message": "Đăng nhập quản trị thành công",
                    **result
                }, 200
            
            except ValueError as e:
                error_code = str(e)
                
                if error_code == "INVALID_CREDENTIALS":
                    return {
                        "status": "error",
                        "error_code": "INVALID_CREDENTIALS",
                        "message": "Sai tên đăng nhập hoặc mật khẩu"
                    }, 401
                elif error_code == "ACCOUNT_LOCKED_OR_INACTIVE":
                    return {
                        "status": "error",
                        "error_code": "ACCOUNT_LOCKED_OR_INACTIVE",
                        "message": "Tài khoản bị khóa hoặc chưa được kích hoạt"
                    }, 403
                else:
                    logger.error(f"Login error: {str(e)}")
                    return {
                        "status": "error",
                        "error_code": "INTERNAL_ERROR",
                        "message": "Lỗi hệ thống"
                    }, 500
    
    # Employee endpoints
    @employees_ns.route('')
    class EmployeeList(Resource):
        @auth_required
        def get(self):
            """View employee list"""
            try:
                employees = employee_service.list_employees()
                
                return {
                    "status": "success",
                    "total": len(employees),
                    "employees": employees
                }, 200
            
            except Exception as e:
                logger.error(f"List employees error: {str(e)}")
                return {
                    "status": "error",
                    "error_code": "INTERNAL_ERROR",
                    "message": "Lỗi hệ thống"
                }, 500
        
        @auth_required
        @admin_required
        @employees_ns.expect(employee_create_model)
        def post(self):
            """Add employee account"""
            data = request.get_json()
            
            if not data or 'full_name' not in data or 'role_id' not in data:
                return {
                    "status": "error",
                    "error_code": "MISSING_FIELDS",
                    "message": "Thiếu thông tin bắt buộc"
                }, 400
            
            try:
                # Generate default password
                # default_password = auth_service.generate_default_password()
                default_password = 'Temp@1234'
                employee = employee_service.create_employee(
                    full_name=data['full_name'],
                    role_id=data['role_id'],
                    default_password=default_password,
                    partner_id=data.get('partner_id')
                )
                
                return {
                    "status": "success",
                    "employee_id": str(employee["_id"]),
                    "message": "Tạo tài khoản nhân viên thành công và đã gửi email kích hoạt"
                }, 201
            
            except ValueError as e:
                error_code = str(e)
                
                if error_code == "EMPLOYEE_ALREADY_EXISTS":
                    return {
                        "status": "error",
                        "error_code": "EMPLOYEE_ALREADY_EXISTS",
                        "message": "Tài khoản nhân viên đã tồn tại"
                    }, 409
                else:
                    logger.error(f"Create employee error: {str(e)}")
                    return {
                        "status": "error",
                        "error_code": "INTERNAL_ERROR",
                        "message": "Lỗi hệ thống"
                    }, 500
    
    @employees_ns.route('/<string:employee_id>')
    class EmployeeDetail(Resource):
        @auth_required
        @admin_required
        @employees_ns.expect(employee_update_model)
        def put(self, employee_id):
            """Update employee account"""
            data = request.get_json()
            
            if not data:
                return {
                    "status": "error",
                    "error_code": "MISSING_FIELDS",
                    "message": "Thiếu thông tin cập nhật"
                }, 400
            
            try:
                employee_service.update_employee(
                    employee_id=employee_id,
                    full_name=data.get('full_name'),
                    role_id=data.get('role_id'),
                    status=data.get('status')
                )
                
                return {
                    "status": "success",
                    "message": "Cập nhật tài khoản nhân viên thành công"
                }, 200
            
            except ValueError as e:
                logger.error(f"Update employee error: {str(e)}")
                return {
                    "status": "error",
                    "error_code": "NOT_FOUND",
                    "message": "Không tìm thấy nhân viên"
                }, 404
        
        @auth_required
        @admin_required
        def delete(self, employee_id):
            """Delete/Disable employee account"""
            lock_only = request.args.get('lock_only', 'false').lower() == 'true'
            
            try:
                result = employee_service.delete_employee(employee_id, lock_only)
                return result, 200
            
            except ValueError as e:
                logger.error(f"Delete employee error: {str(e)}")
                return {
                    "status": "error",
                    "error_code": "NOT_FOUND",
                    "message": "Không tìm thấy nhân viên"
                }, 404
    
    # Add namespaces to API
    api.add_namespace(auth_ns, path='/core-auth')
    api.add_namespace(employees_ns, path='/core-employees')
    
    return blueprint
