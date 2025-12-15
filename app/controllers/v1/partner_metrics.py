"""
H30 Group - Partner Metrics HTTP API Controller

This controller exposes 3 endpoints for Partner Portal to retrieve metrics:
- H30.1: GET /api/v1/partner/metrics/conversations
- H30.2: GET /api/v1/partner/metrics/satisfaction-rate
- H30.3: GET /api/v1/partner/metrics/offload-rate
"""

from flask import request
from flask_restx import Namespace, Resource, fields
from datetime import datetime
from ...utils.auth import jwt_required

#######################################
## STEP 1. DECLARE THE API NAMESPACE ##
#######################################

api = Namespace(
    'partner/metrics',
    description='Partner Metrics API - Provides metrics data for Partner Portal (H30)'
)

####################################
## STEP 2. DEFINE THE MODELS/DTOs ##
####################################

# Error response model
error_response = api.model("ErrorResponse", {
    "status": fields.String(required=True, description="Status: error", example="error"),
    "error_code": fields.String(required=True, description="Error code", example="INVALID_PARAMETERS"),
    "message": fields.String(required=True, description="Error message"),
    "details": fields.String(description="Additional error details")
})

# H30.1 - Conversations response
conversations_response = api.model("ConversationsResponse", {
    "status": fields.String(required=True, description="Status: success", example="success"),
    "total_conversations": fields.Integer(required=True, description="Total number of conversations"),
    "texting_conversations": fields.Integer(required=True, description="Number of texting conversations"),
    "calling_conversations": fields.Integer(required=True, description="Number of calling conversations"),
    "from_date": fields.String(description="Start date filter (ISO 8601)", example="2025-01-01T00:00:00Z"),
    "to_date": fields.String(description="End date filter (ISO 8601)", example="2025-12-12T23:59:59Z")
})

# H30.2 - Satisfaction rate response
satisfaction_distribution = api.model("SatisfactionDistribution", {
    "satisfaction_1": fields.Integer(description="Count of 1-star ratings"),
    "satisfaction_2": fields.Integer(description="Count of 2-star ratings"),
    "satisfaction_3": fields.Integer(description="Count of 3-star ratings"),
    "satisfaction_4": fields.Integer(description="Count of 4-star ratings"),
    "satisfaction_5": fields.Integer(description="Count of 5-star ratings")
})

satisfaction_response = api.model("SatisfactionRateResponse", {
    "status": fields.String(required=True, description="Status: success", example="success"),
    "total_conversations": fields.Integer(required=True, description="Total number of rated conversations"),
    "satisfaction_distribution": fields.Nested(satisfaction_distribution, description="Rating distribution"),
    "average_rating": fields.Float(required=True, description="Average satisfaction rating", example=4.19),
    "from_date": fields.String(description="Start date filter (ISO 8601)", example="2025-01-01T00:00:00Z"),
    "to_date": fields.String(description="End date filter (ISO 8601)", example="2025-12-12T23:59:59Z")
})

# H30.3 - Offload rate response
offload_response = api.model("OffloadRateResponse", {
    "status": fields.String(required=True, description="Status: success", example="success"),
    "total_conversations": fields.Integer(required=True, description="Total number of conversations"),
    "ai_failed_conversation": fields.Integer(required=True, description="Number of AI failed conversations"),
    "offloaded_conversations": fields.Integer(required=True, description="Number of offloaded conversations"),
    "offload_rate_percentage": fields.Float(required=True, description="Offload rate percentage", example=74.57),
    "from_date": fields.String(description="Start date filter (ISO 8601)", example="2025-01-01T00:00:00Z"),
    "to_date": fields.String(description="End date filter (ISO 8601)", example="2025-12-12T23:59:59Z")
})

# Health check response
health_response = api.model("HealthResponse", {
    "status": fields.String(required=True, description="Health status", example="healthy"),
    "partner_id": fields.String(description="Partner ID"),
    "circuit_breaker_state": fields.String(description="Circuit breaker state")
})

##################################
## STEP 3. CONNECT THE SERVICES ##
##################################

from ...services import partner_metrics_service

###################################
## STEP 4. DEFINE THE CONTROLLER ##
###################################

# Query parameters parser for date filters
date_filter_parser = api.parser()
date_filter_parser.add_argument(
    'from_date',
    type=str,
    location='args',
    required=False,
    help='Start date for statistics (ISO 8601 format)'
)
date_filter_parser.add_argument(
    'to_date',
    type=str,
    location='args',
    required=False,
    help='End date for statistics (ISO 8601 format)'
)


def validate_date_params(from_date: str, to_date: str) -> tuple[bool, str]:
    """
    Validate date parameters.
    Returns (is_valid, error_message)
    """
    if from_date:
        try:
            parsed_from = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        except ValueError:
            return False, "Invalid from_date format. Use ISO 8601 format."
    
    if to_date:
        try:
            parsed_to = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        except ValueError:
            return False, "Invalid to_date format. Use ISO 8601 format."
    
    if from_date and to_date:
        parsed_from = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        parsed_to = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        if parsed_from > parsed_to:
            return False, "from_date must be before to_date"
    
    return True, ""


def handle_service_error(result: dict) -> tuple[dict, int]:
    """
    Handle error responses from service layer.
    """
    error_code = result.get("error_code", "INTERNAL_ERROR")
    
    if error_code == "PARTNER_NOT_FOUND":
        return {
            "status": "error",
            "error_code": "PARTNER_NOT_FOUND",
            "message": "Partner not found"
        }, 404
    
    elif error_code == "DB_CONNECTION_ERROR":
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": "Database connection error"
        }, 500
    
    elif error_code == "S08_UNAVAILABLE":
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": "Core Metrics Service unavailable"
        }, 500
    
    else:
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": "An internal server error occurred while retrieving metrics"
        }, 500


@api.route("/conversations")
class ConversationsMetrics(Resource):
    """
    H30.1 - Partner Conversation Statistics
    """
    
    @api.doc(
        description="Get conversation statistics for this partner, including total, texting, and calling conversations.",
        security="Bearer"
    )
    @api.expect(date_filter_parser)
    @api.response(200, "Success", conversations_response)
    @api.response(400, "Bad Request", error_response)
    @api.response(401, "Unauthorized", error_response)
    @api.response(403, "Forbidden", error_response)
    @api.response(500, "Internal Server Error", error_response)
    @jwt_required
    def get(self):
        """Get conversation statistics for this partner"""
        args = date_filter_parser.parse_args()
        from_date = args.get("from_date")
        to_date = args.get("to_date")
        
        # Validate date parameters
        is_valid, error_msg = validate_date_params(from_date, to_date)
        if not is_valid:
            return {
                "status": "error",
                "error_code": "INVALID_PARAMETERS",
                "message": "Invalid query parameters",
                "details": error_msg
            }, 400
        
        # Get data from service
        result = partner_metrics_service.get_conversations(from_date, to_date)
        
        if result.get("status") == "error":
            return handle_service_error(result)
        
        return result, 200


@api.route("/satisfaction-rate")
class SatisfactionRateMetrics(Resource):
    """
    H30.2 - Partner Customer Satisfaction Rate
    """
    
    @api.doc(
        description="Get customer satisfaction distribution for this partner.",
        security="Bearer"
    )
    @api.expect(date_filter_parser)
    @api.response(200, "Success", satisfaction_response)
    @api.response(400, "Bad Request", error_response)
    @api.response(401, "Unauthorized", error_response)
    @api.response(403, "Forbidden", error_response)
    @api.response(500, "Internal Server Error", error_response)
    @jwt_required
    def get(self):
        """Get customer satisfaction distribution for this partner"""
        args = date_filter_parser.parse_args()
        from_date = args.get("from_date")
        to_date = args.get("to_date")
        
        # Validate date parameters
        is_valid, error_msg = validate_date_params(from_date, to_date)
        if not is_valid:
            return {
                "status": "error",
                "error_code": "INVALID_PARAMETERS",
                "message": "Invalid query parameters",
                "details": error_msg
            }, 400
        
        # Get data from service
        result = partner_metrics_service.get_satisfaction_rate(from_date, to_date)
        
        if result.get("status") == "error":
            return handle_service_error(result)
        
        return result, 200


@api.route("/offload-rate")
class OffloadRateMetrics(Resource):
    """
    H30.3 - Partner Offload Rate
    """
    
    @api.doc(
        description="Get consultation offload rate for this partner.",
        security="Bearer"
    )
    @api.expect(date_filter_parser)
    @api.response(200, "Success", offload_response)
    @api.response(400, "Bad Request", error_response)
    @api.response(401, "Unauthorized", error_response)
    @api.response(403, "Forbidden", error_response)
    @api.response(500, "Internal Server Error", error_response)
    @jwt_required
    def get(self):
        """Get consultation offload rate for this partner"""
        args = date_filter_parser.parse_args()
        from_date = args.get("from_date")
        to_date = args.get("to_date")
        
        # Validate date parameters
        is_valid, error_msg = validate_date_params(from_date, to_date)
        if not is_valid:
            return {
                "status": "error",
                "error_code": "INVALID_PARAMETERS",
                "message": "Invalid query parameters",
                "details": error_msg
            }, 400
        
        # Get data from service
        result = partner_metrics_service.get_offload_rate(from_date, to_date)
        
        if result.get("status") == "error":
            return handle_service_error(result)
        
        return result, 200


@api.route("/health")
class HealthCheck(Resource):
    """
    Health check endpoint for monitoring
    """
    
    @api.doc(description="Check service health status")
    @api.response(200, "Healthy", health_response)
    @api.response(503, "Unhealthy", health_response)
    def get(self):
        """Get service health status"""
        result = partner_metrics_service.get_health_status()
        
        if result.get("status") == "healthy":
            return result, 200
        else:
            return result, 503
