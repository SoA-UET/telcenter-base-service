"""
Telcenter Partner Base Service - Main Entry Point
"""
import os
from flask import Flask
from flask_cors import CORS

# Import services
from app.services.s11_local_knowledge_service.LocalKnowledgeService import LocalKnowledgeService

# Import controllers
from app.controllers.v1 import local_knowledge


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    CORS(app)
    
    # Configuration
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
    
    return app


def main():
    """Main entry point"""
    print("[Telcenter Partner] Starting service...")
    
    # Determine which service to run based on environment variable
    service_mode = os.getenv("SERVICE_MODE", "s11")  # Default to S11
    
    if service_mode == "s11":
        print("[Telcenter Partner] Running S11 Local Knowledge Service")
        
        # Initialize S11 service
        s11_service = LocalKnowledgeService()
        
        # Start RabbitMQ listeners (A32 responses, A33 requests)
        s11_service.start_mq_listeners()
        
        # Create Flask app for H28 HTTP API
        app = create_app()
        
        # Initialize controller with service instance
        local_knowledge.init_controller(s11_service)
        
        # Register blueprint
        app.register_blueprint(local_knowledge.get_blueprint())
        
        # Get port from environment
        port = int(os.getenv("S11_PORT", "7011"))
        
        print(f"[S11] HTTP API listening on port {port}")
        print("[S11] RabbitMQ listeners active")
        
        # Run Flask app
        app.run(host="0.0.0.0", port=port, debug=False)
    
    else:
        print(f"[Telcenter Partner] Unknown service mode: {service_mode}")
        print("Available modes: s11")


if __name__ == "__main__":
    main()
