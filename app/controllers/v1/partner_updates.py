from flask import request, jsonify
from flask_restx import Namespace, Resource, fields
import jwt
import os
from typing import Optional

#######################################
## STEP 1. DECLARE THE API NAMESPACE ##
#######################################

api = Namespace('partner-updates', 'Quản lý các bản cập nhật kiến thức từ Partner')

####################################
## STEP 2. DEFINE THE MODELS/DTOs ##
####################################

# Model for validation task in list
validation_task_summary = api.model("ValidationTaskSummary", {
    "id": fields.String(readonly=True, description="ID của bản cập nhật"),
    "partner_id": fields.String(description="ID của partner gửi cập nhật"),
    "status": fields.String(description="Trạng thái: pending, approved, rejected"),
    "validator_id": fields.String(description="ID người duyệt"),
    "created_at": fields.String(description="Thời gian tạo (ISO 8601)"),
    "validated_at": fields.String(description="Thời gian duyệt (ISO 8601)"),
})

# Model for FAQ
faq_model = api.model("FAQ", {
    "question": fields.String(description="Câu hỏi"),
    "answer": fields.String(description="Câu trả lời"),
})

# Model for package
package_model = api.model("Package", {
    "Mã dịch vụ": fields.String(),
    "Thời gian thanh toán": fields.String(),
    "Các dịch vụ tiên quyết": fields.String(),
    "Giá (VNĐ)": fields.Float(),
    "Chu kỳ (ngày)": fields.Integer(),
    "4G tốc độ tiêu chuẩn/ngày": fields.Float(),
    "4G tốc độ cao/ngày": fields.Float(),
    "4G tốc độ tiêu chuẩn/chu kỳ": fields.Float(),
    "4G tốc độ cao/chu kỳ": fields.Float(),
    "Gọi nội mạng": fields.String(),
    "Gọi ngoại mạng": fields.String(),
    "Tin nhắn": fields.String(),
    "Chi tiết": fields.String(),
    "Tự động gia hạn": fields.String(),
    "Cú pháp đăng ký": fields.String(),
})

# Model for validation task detail
validation_task_detail = api.clone("ValidationTaskDetail", validation_task_summary, {
    "faqs": fields.List(fields.Nested(faq_model), description="Danh sách FAQ"),
    "packages": fields.List(fields.Nested(package_model), description="Danh sách gói cước"),
})

# Model for summary statistics
summary_model = api.model("Summary", {
    "total": fields.Integer(description="Tổng số bản cập nhật"),
    "pending": fields.Integer(description="Số bản đang chờ duyệt"),
    "approved": fields.Integer(description="Số bản đã duyệt"),
    "rejected": fields.Integer(description="Số bản đã từ chối"),
})

# Response models
list_response = api.model("ListResponse", {
    "status": fields.String(description="Trạng thái phản hồi"),
    "total_count": fields.Integer(description="Tổng số bản cập nhật"),
    "page": fields.Integer(description="Trang hiện tại"),
    "limit": fields.Integer(description="Số items mỗi trang"),
    "total_pages": fields.Integer(description="Tổng số trang"),
    "updates": fields.List(fields.Nested(validation_task_summary)),
    "summary": fields.Nested(summary_model),
})

detail_response = api.model("DetailResponse", {
    "status": fields.String(description="Trạng thái phản hồi"),
    "update": fields.Nested(validation_task_detail),
})

approve_reject_response = api.model("ApproveRejectResponse", {
    "status": fields.String(description="Trạng thái phản hồi"),
    "update": fields.Nested(validation_task_summary),
})


###################################
## STEP 3. HELPER FUNCTIONS      ##
###################################

def get_user_id_from_jwt() -> Optional[str]:
    """Extract user ID from JWT token in Authorization header"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    
    try:
        # JWT secret should be configured in environment
        jwt_secret = os.getenv('JWT_SECRET', 'your-secret-key')
        decoded = jwt.decode(token, jwt_secret, algorithms=['HS256'])
        return decoded.get('user_id') or decoded.get('sub')
    except jwt.InvalidTokenError:
        return None


def verify_jwt():
    """Verify JWT token and return user_id"""
    user_id = get_user_id_from_jwt()
    if not user_id:
        api.abort(401, "Unauthorized: Invalid or missing JWT token")
    return user_id


###################################
## STEP 4. DEFINE THE ROUTES     ##
###################################

# Service instance will be injected by the main app
knowledge_validator_service = None

def set_service(service):
    """Set the service instance"""
    global knowledge_validator_service
    knowledge_validator_service = service


@api.route('')
class PartnerUpdatesList(Resource):
    """List partner updates with filtering and pagination"""
    
    @api.doc('list_partner_updates')
    @api.doc(security='Bearer Auth')
    @api.param('status', 'Filter by status (pending, approved, rejected)', required=False)
    @api.param('partner_id', 'Filter by partner ID', required=False)
    @api.param('pageNumber', 'Page number (default: 1)', type=int, required=False)
    @api.param('pageSize', 'Items per page (default: 20, max: 100)', type=int, required=False)
    @api.marshal_with(list_response)
    def get(self):
        """Lấy danh sách các bản cập nhật từ Partners"""
        # Verify JWT
        verify_jwt()
        
        # Get query parameters
        status = request.args.get('status', None)
        partner_id = request.args.get('partner_id', None)
        page = int(request.args.get('pageNumber', 1))
        page_size = int(request.args.get('pageSize', 20))
        
        # Validate page_size
        if page_size > 100:
            page_size = 100
        if page_size < 1:
            page_size = 20
        if page < 1:
            page = 1
        
        # Get tasks from service
        result = knowledge_validator_service.get_validation_tasks(
            status=status,
            partner_id=partner_id,
            page=page,
            limit=page_size
        )
        
        return result, 200


@api.route('/<string:update_id>')
@api.param('update_id', 'ID của bản cập nhật')
class PartnerUpdateDetail(Resource):
    """Get, approve, or reject a specific partner update"""
    
    @api.doc('get_partner_update')
    @api.doc(security='Bearer Auth')
    @api.marshal_with(detail_response)
    def get(self, update_id):
        """Lấy thông tin chi tiết của một bản cập nhật"""
        # Verify JWT
        verify_jwt()
        
        # Get task from service
        task = knowledge_validator_service.get_validation_task_by_id(update_id)
        
        if not task:
            api.abort(404, f"Update {update_id} not found")
        
        return {
            "status": "success",
            "update": task
        }, 200


@api.route('/<string:update_id>/approve')
@api.param('update_id', 'ID của bản cập nhật cần duyệt')
class PartnerUpdateApprove(Resource):
    """Approve a partner update"""
    
    @api.doc('approve_partner_update')
    @api.doc(security='Bearer Auth')
    @api.marshal_with(approve_reject_response)
    def post(self, update_id):
        """Duyệt một bản cập nhật từ Partner"""
        # Verify JWT and get validator_id
        validator_id = verify_jwt()
        
        # Approve the task
        updated_task = knowledge_validator_service.approve_validation_task(
            update_id, 
            validator_id
        )
        
        if not updated_task:
            api.abort(404, f"Update {update_id} not found or already processed")
        
        return {
            "status": "success",
            "update": updated_task
        }, 200


@api.route('/<string:update_id>/reject')
@api.param('update_id', 'ID của bản cập nhật cần từ chối')
class PartnerUpdateReject(Resource):
    """Reject a partner update"""
    
    @api.doc('reject_partner_update')
    @api.doc(security='Bearer Auth')
    @api.marshal_with(approve_reject_response)
    def post(self, update_id):
        """Từ chối một bản cập nhật từ Partner"""
        # Verify JWT and get validator_id
        validator_id = verify_jwt()
        
        # Reject the task
        updated_task = knowledge_validator_service.reject_validation_task(
            update_id,
            validator_id
        )
        
        if not updated_task:
            api.abort(404, f"Update {update_id} not found or already processed")
        
        return {
            "status": "success",
            "update": updated_task
        }, 200
