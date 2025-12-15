"""
S14 Partner Metrics Service - Entry Point

This service aggregates and provides 3 main types of metrics for the Partner Portal:
1. Total Active Conversations with Partner Consultants (H30.1)
2. Customer Satisfaction Rate (H30.2)
3. Partner Offload Rate (H30.3)

The service operates in two modes:
- Real-time metrics collection via events from Core S08 (background processing via A17a)
- Responding to HTTP requests (on-demand queries via H30)
"""

import os
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from flask import Flask
from flask_cors import CORS


def create_app() -> Flask:
    """
    Create and configure the Flask application.
    """
    app = Flask(__name__)
    
    # Enable CORS
    CORS(app)
    
    # Configure app
    app.config['RESTX_MASK_SWAGGER'] = False
    
    # Register API blueprints
    from .controllers import register_api_controllers
    from flask_socketio import SocketIO
    
    socketio = SocketIO(app, cors_allowed_origins="*")
    register_api_controllers(app, socketio)
    
    return app


def start_background_services():
    """
    Start background services (RabbitMQ consumers) in separate threads.
    """
    from .services import partner_metrics_service
    
    # Start the partner metrics service (initializes RabbitMQ connections and workers)
    try:
        partner_metrics_service.start()
        print("[S14] Background services started successfully")
    except Exception as e:
        print(f"[S14] Failed to start background services: {e}")
        raise


def main():
    """
    Main entry point for S14 Partner Metrics Service.
    """
    print("=" * 60)
    print("S14 Partner Metrics Service")
    print("=" * 60)
    
    # Get configuration
    port = int(os.getenv("PARTNER_METRICS_SERVICE_PORT", "5014"))
    partner_id = os.getenv("PARTNER_ID", "")
    
    print(f"Partner ID: {partner_id}")
    print(f"HTTP Port: {port}")
    print("=" * 60)
    
    # Start background services in a separate thread
    background_thread = threading.Thread(
        target=start_background_services,
        daemon=True
    )
    background_thread.start()
    
    # Create Flask app
    app = create_app()
    
    # Run Flask app (blocking)
    print(f"[S14] Starting HTTP server on port {port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        threaded=True
    )


if __name__ == "__main__":
    main()
