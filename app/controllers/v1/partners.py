"""
Partners Controller for S07 Partner Management Service.

HTTP APIs:
- H24: Core Portal -> S07 (CRUD operations for partners)
- H11: S09 -> S07 (Verify partner connection)

All H24 endpoints require JWT authentication.
H11 endpoint uses API key authentication.
"""

from flask import request
from flask_restx import Namespace, Resource, fields
from ..common.models import timing_enabled
from ...utils.auth import jwt_required

#######################################
## STEP 1. DECLARE THE API NAMESPACE ##
#######################################

api = Namespace('partners', description='Partner Management Service - Quản lý kết nối với các Partner telecom.')

####################################
## STEP 2. DEFINE THE MODELS/DTOs ##
####################################

# H24: Request DTOs
partner_create_dto = api.model("PartnerCreate", {
    "name": fields.String(required=True, description="Tên nhà mạng (VD: Vinaphone, Viettel)"),
    "base_url": fields.String(required=True, description="Endpoint API của hệ thống Partner"),
})

partner_update_dto = api.model("PartnerUpdate", {
    "name": fields.String(required=False, description="Tên nhà mạng mới"),
    "api_key": fields.String(required=False, description="API key mới"),
    "base_url": fields.String(required=False, description="Endpoint API mới"),
})

# H24: Response DTOs
partner_dto = api.model("Partner", {
    "id": fields.String(readonly=True, description="ID định danh nhà mạng"),
    "name": fields.String(description="Tên nhà mạng"),
    "base_url": fields.String(description="Endpoint API của hệ thống Partner"),
    "api_key": fields.String(description="API key để xác thực"),
    **timing_enabled,
})

success_response = api.model("SuccessResponse", {
    "status": fields.String(description="Status: success", example="success"),
    "data": fields.Raw(description="Response data"),
})

success_list_response = api.model("SuccessListResponse", {
    "status": fields.String(description="Status: success", example="success"),
    "data": fields.List(fields.Nested(partner_dto), description="List of partners"),
})

error_response = api.model("ErrorResponse", {
    "status": fields.String(description="Status: error", example="error"),
    "message": fields.String(description="Error message"),
})

# H11: Response DTOs
verify_connection_response = api.model("VerifyConnectionResponse", {
    "status": fields.String(description="Status: success"),
    "data": fields.Nested(api.model("VerifyConnectionData", {
        "partner_id": fields.String(description="Partner ID that was verified"),
    })),
})

##################################
## STEP 3. CONNECT THE SERVICES ##
##################################

from ...services import partner_service

###################################
## STEP 4. DEFINE THE CONTROLLER ##
## H24 API - Core Portal → S07  ##
###################################

@api.route("/")
class PartnersCollection(Resource):
    """
    H24 API: Partner Collection endpoints.
    GET - List all partners
    POST - Create new partner
    """
    
    @api.doc(
        description="[H24] Lấy danh sách tất cả các Partner connections.",
        security='Bearer Auth'
    )
    @api.response(200, 'Success', success_list_response)
    @api.response(401, 'Unauthorized', error_response)
    @jwt_required
    def get(self):
        """Get list of all Partner connections"""
        try:
            partners = partner_service.get_all_partners()
            return {
                "status": "success",
                "data": partners
            }, 200
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }, 500
    
    @api.doc(
        description="[H24] Tạo mới Partner connection (TC-03.1).",
        security='Bearer Auth'
    )
    @api.expect(partner_create_dto)
    @api.response(200, 'Success', success_response)
    @api.response(400, 'Bad Request', error_response)
    @api.response(401, 'Unauthorized', error_response)
    @jwt_required
    def post(self):
        """Create a new Partner connection"""
        try:
            data = request.get_json()
            partner = partner_service.create_partner(data)
            return {
                "status": "success",
                "data": partner
            }, 200
        except Exception as e:
            error_msg = str(e)
            if "Partner already exists" in error_msg or "400" in error_msg:
                return {
                    "status": "error",
                    "message": "Partner already exists"
                }, 400
            return {
                "status": "error",
                "message": error_msg
            }, 500


@api.route("/<string:id>")
class PartnerItem(Resource):
    """
    H24 API: Partner Item endpoints.
    PATCH - Update partner
    DELETE - Delete partner
    """
    
    @api.doc(
        description="[H24] Cập nhật Partner connection (TC-03.2).",
        security='Bearer Auth'
    )
    @api.expect(partner_update_dto)
    @api.response(200, 'Success', success_response)
    @api.response(400, 'Bad Request', error_response)
    @api.response(401, 'Unauthorized', error_response)
    @api.response(404, 'Not Found', error_response)
    @jwt_required
    def patch(self, id):
        """Update an existing Partner connection"""
        try:
            data = request.get_json()
            partner = partner_service.update_partner(id, data)
            return {
                "status": "success",
                "data": partner
            }, 200
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                return {
                    "status": "error",
                    "message": "Partner not found"
                }, 404
            if "400" in error_msg:
                return {
                    "status": "error",
                    "message": error_msg
                }, 400
            return {
                "status": "error",
                "message": error_msg
            }, 500
    
    @api.doc(
        description="[H24] Xóa Partner connection (TC-03.3).",
        security='Bearer Auth'
    )
    @api.response(200, 'Success')
    @api.response(401, 'Unauthorized', error_response)
    @api.response(404, 'Not Found', error_response)
    @jwt_required
    def delete(self, id):
        """Delete a Partner connection"""
        try:
            partner_service.delete_partner(id)
            return {
                "status": "success"
            }, 200
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                return {
                    "status": "error",
                    "message": "Partner not found"
                }, 404
            return {
                "status": "error",
                "message": error_msg
            }, 500


###################################
## H11 API - S09 → S07           ##
## Verify Partner Connection     ##
###################################

@api.route("/<string:id>/verify-connection")
class VerifyPartnerConnection(Resource):
    """
    H11 API: Verify partner connection endpoint.
    POST - Verify the Core connection using API key.
    """
    
    @api.doc(
        description="[H11] Verify the Core connection. Partner system (S09) gọi endpoint này để xác thực kết nối.",
    )
    @api.response(200, 'Success', verify_connection_response)
    @api.response(401, 'Unauthorized', error_response)
    @api.response(404, 'Not Found', error_response)
    def post(self, id):
        """Verify partner connection using API key"""
        try:
            # Extract API key from Authorization header
            auth_header = request.headers.get('Authorization', '')
            
            if not auth_header:
                return {
                    "status": "error",
                    "message": "Missing Authorization header"
                }, 401
            
            # Parse "Bearer <API_key>"
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return {
                    "status": "error",
                    "message": "Invalid Authorization header format"
                }, 401
            
            api_key = parts[1]
            
            # Verify the connection
            result = partner_service.verify_partner_connection(id, api_key)
            
            return {
                "status": "success",
                "data": result
            }, 200
        
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Invalid API key" in error_msg:
                return {
                    "status": "error",
                    "message": "Invalid API key"
                }, 401
            if "404" in error_msg:
                return {
                    "status": "error",
                    "message": "Partner not found"
                }, 404
            return {
                "status": "error",
                "message": error_msg
            }, 500
