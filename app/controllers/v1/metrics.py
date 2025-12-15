"""
H21 HTTP Endpoints for Metrics Service.

Provides 5 endpoints for the Core Portal:
1. GET /api/v1/metrics/users/total - Total customers
2. GET /api/v1/core/metrics/conversations/summary - Conversation summary
3. GET /api/v1/core/metrics/consultations/satisfaction - Satisfaction distribution
4. GET /api/v1/core/metrics/consultations/offload-rate - Overall offload rate
5. GET /api/v1/core/metrics/consultations/offload-rate-by-partner - Per-partner offload rate
"""

from datetime import datetime
from flask import request
from flask_restx import Namespace, Resource, fields

from ...utils.auth import jwt_required
from ...services.MetricsService import (
    ServiceUnavailableError,
    DatabaseTimeoutError,
    DatabaseConnectionError,
    ServiceError,
)

#######################################
## API NAMESPACE FOR METRICS         ##
#######################################

api = Namespace('metrics', 'Core Portal Metrics APIs (H21)')

####################################
## RESPONSE MODELS                ##
####################################

# Error response model
error_response = api.model("ErrorResponse", {
    "status": fields.String(description="Status", example="error"),
    "error_code": fields.String(description="Error code"),
    "message": fields.String(description="Error message"),
    "details": fields.String(description="Additional details", required=False),
})

# H21.1 - Total Users Response
total_users_response = api.model("TotalUsersResponse", {
    "status": fields.String(description="Status", example="success"),
    "total_customers": fields.Integer(description="Total number of registered customers"),
    "from_date": fields.String(description="Start date filter (ISO 8601)", required=False),
    "to_date": fields.String(description="End date filter (ISO 8601)", required=False),
})

# H21.2 - Conversation Summary Response
conversation_summary_response = api.model("ConversationSummaryResponse", {
    "status": fields.String(description="Status", example="success"),
    "total_conversations": fields.Integer(description="Total number of conversations"),
    "texting_conversations": fields.Integer(description="Number of text-based conversations"),
    "calling_conversations": fields.Integer(description="Number of calling conversations"),
    "from_date": fields.String(description="Start date filter (ISO 8601)", required=False),
    "to_date": fields.String(description="End date filter (ISO 8601)", required=False),
})

# H21.3 - Satisfaction Distribution Response
satisfaction_distribution_model = api.model("SatisfactionDistribution", {
    "satisfaction_1": fields.Integer(description="Count of 1-star ratings"),
    "satisfaction_2": fields.Integer(description="Count of 2-star ratings"),
    "satisfaction_3": fields.Integer(description="Count of 3-star ratings"),
    "satisfaction_4": fields.Integer(description="Count of 4-star ratings"),
    "satisfaction_5": fields.Integer(description="Count of 5-star ratings"),
})

satisfaction_response = api.model("SatisfactionResponse", {
    "status": fields.String(description="Status", example="success"),
    "total_conversations": fields.Integer(description="Total number of rated conversations"),
    "satisfaction_distribution": fields.Nested(satisfaction_distribution_model),
    "average_rating": fields.Float(description="Average satisfaction rating"),
    "from_date": fields.String(description="Start date filter (ISO 8601)", required=False),
    "to_date": fields.String(description="End date filter (ISO 8601)", required=False),
})

# H21.4 - Offload Rate Response
offload_rate_response = api.model("OffloadRateResponse", {
    "status": fields.String(description="Status", example="success"),
    "total_conversations": fields.Integer(description="Total number of conversations"),
    "ai_failed_conversation": fields.Integer(description="Number of AI-failed conversations"),
    "offloaded_conversations": fields.Integer(description="Number of offloaded (AI-handled) conversations"),
    "offload_rate_percentage": fields.Float(description="Percentage of conversations offloaded"),
    "from_date": fields.String(description="Start date filter (ISO 8601)", required=False),
    "to_date": fields.String(description="End date filter (ISO 8601)", required=False),
})

# H21.5 - Partner Offload Rate Response
partner_stats_model = api.model("PartnerStats", {
    "partner_id": fields.String(description="Partner ID"),
    "partner_name": fields.String(description="Partner display name"),
    "total_conversations": fields.Integer(description="Total conversations for this partner"),
    "offloaded_conversations": fields.Integer(description="Offloaded conversations for this partner"),
    "ai_failed_conversations": fields.Integer(description="AI-failed conversations for this partner"),
    "offload_rate_percentage": fields.Float(description="Offload rate for this partner"),
})

offload_rate_by_partner_response = api.model("OffloadRateByPartnerResponse", {
    "status": fields.String(description="Status", example="success"),
    "total_consultations": fields.Integer(description="Total consultations across all partners"),
    "partners": fields.List(fields.Nested(partner_stats_model)),
    "overall_offload_rate_percentage": fields.Float(description="Overall offload rate"),
    "from_date": fields.String(description="Start date filter (ISO 8601)", required=False),
    "to_date": fields.String(description="End date filter (ISO 8601)", required=False),
})

##################################
## CONNECT THE SERVICES         ##
##################################

# Will be imported and set in __init__.py
metrics_service = None

def set_metrics_service(service):
    """Set the metrics service instance"""
    global metrics_service
    metrics_service = service

def get_metrics_service():
    """Get the metrics service instance"""
    global metrics_service
    if metrics_service is None:
        # Lazy import to avoid circular imports
        from ...services import metrics_service as ms
        metrics_service = ms
    return metrics_service

##################################
## HELPER FUNCTIONS             ##
##################################

def parse_date_params():
    """Parse from_date and to_date query parameters"""
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    
    # Validate date format if provided
    if from_date:
        try:
            datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        except ValueError:
            return None, None, "Invalid from_date format. Use ISO 8601 format."
    
    if to_date:
        try:
            datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        except ValueError:
            return None, None, "Invalid to_date format. Use ISO 8601 format."
    
    # Validate date range
    if from_date and to_date:
        from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        if from_dt > to_dt:
            return None, None, "from_date must be before to_date"
    
    return from_date, to_date, None


def handle_service_error(e: Exception):
    """Convert service exceptions to HTTP responses"""
    if isinstance(e, ServiceUnavailableError):
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": str(e)
        }, 500
    elif isinstance(e, DatabaseTimeoutError):
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": str(e)
        }, 500
    elif isinstance(e, DatabaseConnectionError):
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": str(e)
        }, 500
    elif isinstance(e, ServiceError):
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": "An internal server error occurred while retrieving metrics"
        }, 500
    else:
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": "An internal server error occurred while retrieving metrics"
        }, 500


###################################
## H21.1 - TOTAL USERS           ##
###################################

@api.route("/users/total")
class TotalUsers(Resource):
    """H21.1 - Get total number of registered users"""
    
    @api.doc(
        description="Get total number of users registered in the system",
        security="Bearer",
        params={
            "from_date": "Start date for counting users (ISO 8601 format)",
            "to_date": "End date for counting users (ISO 8601 format)",
        }
    )
    @api.response(200, "Success", total_users_response)
    @api.response(400, "Bad Request", error_response)
    @api.response(401, "Unauthorized", error_response)
    @api.response(500, "Internal Server Error", error_response)
    @jwt_required
    def get(self):
        """Get total customers count"""
        # Parse date parameters
        from_date, to_date, error = parse_date_params()
        if error:
            return {
                "status": "error",
                "error_code": "INVALID_PARAMETERS",
                "message": "Invalid query parameters",
                "details": error
            }, 400
        
        try:
            service = get_metrics_service()
            result = service.get_total_customers()
            
            # Add date filters to response
            if from_date:
                result["from_date"] = from_date
            if to_date:
                result["to_date"] = to_date
            
            return result, 200
            
        except ServiceError as e:
            return handle_service_error(e)
        except Exception as e:
            print(f"[MetricsController] Error in get_total_users: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }, 500


###################################
## CORE METRICS NAMESPACE        ##
###################################

core_metrics_api = Namespace('core/metrics', 'Core Metrics APIs (H21.2-H21.5)')


###################################
## H21.2 - CONVERSATION SUMMARY  ##
###################################

@core_metrics_api.route("/conversations/summary")
class ConversationSummary(Resource):
    """H21.2 - Get conversation statistics summary"""
    
    @core_metrics_api.doc(
        description="Get conversation statistics including total, texting, and calling conversations",
        security="Bearer",
        params={
            "from_date": "Start date for conversation statistics (ISO 8601 format)",
            "to_date": "End date for conversation statistics (ISO 8601 format)",
        }
    )
    @core_metrics_api.response(200, "Success", conversation_summary_response)
    @core_metrics_api.response(400, "Bad Request", error_response)
    @core_metrics_api.response(401, "Unauthorized", error_response)
    @core_metrics_api.response(500, "Internal Server Error", error_response)
    @jwt_required
    def get(self):
        """Get conversation summary"""
        # Parse date parameters
        from_date, to_date, error = parse_date_params()
        if error:
            return {
                "status": "error",
                "error_code": "INVALID_PARAMETERS",
                "message": "Invalid query parameters",
                "details": error
            }, 400
        
        try:
            service = get_metrics_service()
            result = service.get_conversation_summary()
            
            # Add date filters to response
            if from_date:
                result["from_date"] = from_date
            if to_date:
                result["to_date"] = to_date
            
            return result, 200
            
        except ServiceError as e:
            return handle_service_error(e)
        except Exception as e:
            print(f"[MetricsController] Error in get_conversation_summary: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }, 500


###################################
## H21.3 - SATISFACTION DIST.    ##
###################################

@core_metrics_api.route("/consultations/satisfaction")
class SatisfactionDistribution(Resource):
    """H21.3 - Get customer satisfaction distribution"""
    
    @core_metrics_api.doc(
        description="Get distribution of consultation sessions by customer satisfaction rating (1-5 stars)",
        security="Bearer",
        params={
            "from_date": "Start date for consultation statistics (ISO 8601 format)",
            "to_date": "End date for consultation statistics (ISO 8601 format)",
        }
    )
    @core_metrics_api.response(200, "Success", satisfaction_response)
    @core_metrics_api.response(400, "Bad Request", error_response)
    @core_metrics_api.response(401, "Unauthorized", error_response)
    @core_metrics_api.response(500, "Internal Server Error", error_response)
    @jwt_required
    def get(self):
        """Get satisfaction distribution"""
        # Parse date parameters
        from_date, to_date, error = parse_date_params()
        if error:
            return {
                "status": "error",
                "error_code": "INVALID_PARAMETERS",
                "message": "Invalid query parameters",
                "details": error
            }, 400
        
        try:
            service = get_metrics_service()
            result = service.get_satisfaction_distribution()
            
            # Add date filters to response
            if from_date:
                result["from_date"] = from_date
            if to_date:
                result["to_date"] = to_date
            
            return result, 200
            
        except ServiceError as e:
            return handle_service_error(e)
        except Exception as e:
            print(f"[MetricsController] Error in get_satisfaction_distribution: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }, 500


###################################
## H21.4 - OFFLOAD RATE          ##
###################################

@core_metrics_api.route("/consultations/offload-rate")
class OffloadRate(Resource):
    """H21.4 - Get overall offload rate"""
    
    @core_metrics_api.doc(
        description="Get rate of consultation sessions successfully offloaded (handled by AI without human intervention)",
        security="Bearer",
        params={
            "from_date": "Start date for consultation statistics (ISO 8601 format)",
            "to_date": "End date for consultation statistics (ISO 8601 format)",
        }
    )
    @core_metrics_api.response(200, "Success", offload_rate_response)
    @core_metrics_api.response(400, "Bad Request", error_response)
    @core_metrics_api.response(401, "Unauthorized", error_response)
    @core_metrics_api.response(500, "Internal Server Error", error_response)
    @jwt_required
    def get(self):
        """Get offload rate"""
        # Parse date parameters
        from_date, to_date, error = parse_date_params()
        if error:
            return {
                "status": "error",
                "error_code": "INVALID_PARAMETERS",
                "message": "Invalid query parameters",
                "details": error
            }, 400
        
        try:
            service = get_metrics_service()
            result = service.get_offload_rate()
            
            # Add date filters to response
            if from_date:
                result["from_date"] = from_date
            if to_date:
                result["to_date"] = to_date
            
            return result, 200
            
        except ServiceError as e:
            return handle_service_error(e)
        except Exception as e:
            print(f"[MetricsController] Error in get_offload_rate: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }, 500


###################################
## H21.5 - OFFLOAD RATE BY PARTNER
###################################

@core_metrics_api.route("/consultations/offload-rate-by-partner")
class OffloadRateByPartner(Resource):
    """H21.5 - Get offload rate by partner"""
    
    @core_metrics_api.doc(
        description="Get rate of offloaded consultation sessions broken down by partner",
        security="Bearer",
        params={
            "from_date": "Start date for consultation statistics (ISO 8601 format)",
            "to_date": "End date for consultation statistics (ISO 8601 format)",
            "partner_id": "Filter by specific partner ID",
        }
    )
    @core_metrics_api.response(200, "Success", offload_rate_by_partner_response)
    @core_metrics_api.response(400, "Bad Request", error_response)
    @core_metrics_api.response(401, "Unauthorized", error_response)
    @core_metrics_api.response(500, "Internal Server Error", error_response)
    @jwt_required
    def get(self):
        """Get offload rate by partner"""
        # Parse date parameters
        from_date, to_date, error = parse_date_params()
        if error:
            return {
                "status": "error",
                "error_code": "INVALID_PARAMETERS",
                "message": "Invalid query parameters",
                "details": error
            }, 400
        
        # Get partner_id filter
        partner_id = request.args.get("partner_id")
        
        try:
            service = get_metrics_service()
            result = service.get_offload_rate_by_partner(partner_id_filter=partner_id)
            
            # Add date filters to response
            if from_date:
                result["from_date"] = from_date
            if to_date:
                result["to_date"] = to_date
            
            return result, 200
            
        except ServiceError as e:
            return handle_service_error(e)
        except Exception as e:
            print(f"[MetricsController] Error in get_offload_rate_by_partner: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }, 500


###################################
## HEALTH CHECK ENDPOINT         ##
###################################

@api.route("/health")
class HealthCheck(Resource):
    """Health check endpoint for S08 Metrics Service"""
    
    @api.doc(description="Check service health status")
    def get(self):
        """Get service health status"""
        try:
            service = get_metrics_service()
            is_healthy = service.is_healthy()
            
            if is_healthy:
                return {"status": "healthy"}, 200
            else:
                return {"status": "unhealthy"}, 503
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}, 503
