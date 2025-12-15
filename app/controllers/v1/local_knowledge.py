"""
H28 HTTP API Controller for S11 Local Knowledge Service
Handles Partner Portal requests for CRUD operations on packages/FAQs and file imports
"""
from flask import Blueprint, request, jsonify
from typing import Dict, Any
from ..s11_local_knowledge_service.LocalKnowledgeService import LocalKnowledgeService


# Create blueprint
local_knowledge_bp = Blueprint('local_knowledge', __name__, url_prefix='/api/v1/local-knowledge')

# Service instance (will be injected)
service: LocalKnowledgeService = None


def init_controller(local_knowledge_service: LocalKnowledgeService):
    """Initialize controller with service instance"""
    global service
    service = local_knowledge_service


def create_json_rpc_response(request_id: str, status: str, content: Any) -> Dict:
    """Create a JSON-RPC style response"""
    return {
        "id": request_id,
        "result": {
            "status": status,
            "content": content
        }
    }


def create_error_response(request_id: str, error_message: str) -> Dict:
    """Create an error response"""
    return create_json_rpc_response(request_id, "error", error_message)


@local_knowledge_bp.route('/packages', methods=['POST'])
def crud_packages():
    """
    H28 Method: crud_packages
    Handle CRUD operations for packages
    """
    try:
        data = request.get_json()
        
        # Validate request structure
        if not data or "method" not in data or "params" not in data or "id" not in data:
            return jsonify(create_error_response("unknown", "Invalid request format")), 400
        
        request_id = data.get("id")
        params = data.get("params", {})
        action = params.get("action")
        
        # Validate action
        valid_actions = ["list", "create", "update", "delete"]
        if action not in valid_actions:
            return jsonify(create_error_response(
                request_id,
                f"Invalid action. Must be one of: {', '.join(valid_actions)}"
            )), 400
        
        # Get data
        action_data = params.get("data", {})
        
        # Execute action
        try:
            if action == "list":
                result = service.list_packages(action_data)
            elif action == "create":
                result = service.create_package(action_data)
            elif action == "update":
                result = service.update_package(action_data)
            elif action == "delete":
                result = service.delete_package(action_data)
            
            return jsonify(create_json_rpc_response(request_id, "success", result)), 200
            
        except ValueError as e:
            return jsonify(create_error_response(request_id, str(e))), 400
        except Exception as e:
            return jsonify(create_error_response(request_id, str(e))), 500
    
    except Exception as e:
        return jsonify(create_error_response("unknown", str(e))), 500


@local_knowledge_bp.route('/faqs', methods=['POST'])
def crud_faqs():
    """
    H28 Method: crud_faqs
    Handle CRUD operations for FAQs
    """
    try:
        data = request.get_json()
        
        # Validate request structure
        if not data or "method" not in data or "params" not in data or "id" not in data:
            return jsonify(create_error_response("unknown", "Invalid request format")), 400
        
        request_id = data.get("id")
        params = data.get("params", {})
        action = params.get("action")
        
        # Validate action
        valid_actions = ["list", "create", "update", "delete"]
        if action not in valid_actions:
            return jsonify(create_error_response(
                request_id,
                f"Invalid action. Must be one of: {', '.join(valid_actions)}"
            )), 400
        
        # Get data
        action_data = params.get("data", {})
        
        # Execute action
        try:
            if action == "list":
                result = service.list_faqs(action_data)
            elif action == "create":
                result = service.create_faq(action_data)
            elif action == "update":
                result = service.update_faq(action_data)
            elif action == "delete":
                result = service.delete_faq(action_data)
            
            return jsonify(create_json_rpc_response(request_id, "success", result)), 200
            
        except ValueError as e:
            return jsonify(create_error_response(request_id, str(e))), 400
        except Exception as e:
            return jsonify(create_error_response(request_id, str(e))), 500
    
    except Exception as e:
        return jsonify(create_error_response("unknown", str(e))), 500


@local_knowledge_bp.route('/import-file', methods=['POST'])
def import_file():
    """
    H28 Method: import_file
    Handle file import for bulk knowledge data
    Accepts multipart/form-data with file and optional metadata
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify(create_error_response(
                "unknown",
                "No file provided"
            )), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify(create_error_response(
                "unknown",
                "Empty filename"
            )), 400
        
        # Validate file format
        allowed_extensions = ['.pdf', '.xlsx', '.xls', '.docx']
        file_ext = None
        for ext in allowed_extensions:
            if file.filename.lower().endswith(ext):
                file_ext = ext
                break
        
        if not file_ext:
            return jsonify(create_error_response(
                "unknown",
                f"Unsupported file format. Supported: {', '.join(allowed_extensions)}"
            )), 400
        
        # Check file size (50MB limit)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Seek back to start
        
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            return jsonify(create_error_response(
                "unknown",
                "File size exceeds maximum limit of 50MB"
            )), 400
        
        # Read file content
        file_content = file.read()
        
        # Get metadata if provided
        metadata = {}
        if 'metadata' in request.form:
            import json
            metadata = json.loads(request.form['metadata'])
        
        # Generate request ID
        import time
        request_id = f"h28-import-{int(time.time() * 1000)}"
        
        # Process file import
        try:
            result = service.import_file(file_content, file.filename, metadata)
            return jsonify(create_json_rpc_response(request_id, "success", result)), 200
        except ValueError as e:
            return jsonify(create_error_response(request_id, str(e))), 400
        except Exception as e:
            return jsonify(create_error_response(request_id, str(e))), 500
    
    except Exception as e:
        return jsonify(create_error_response("unknown", str(e))), 500


def get_blueprint():
    """Get the Flask blueprint for this controller"""
    return local_knowledge_bp
