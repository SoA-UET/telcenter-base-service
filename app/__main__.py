"""
S08 Metrics Service - Main Entry Point

This is the main entry point for the S08 Metrics Service.
It starts both the HTTP server (Flask) and the RabbitMQ event consumers.
"""

import os
import threading
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, redirect
from flask_cors import CORS
from flask_restx import Api

from app.services.MetricsService import MetricsService
from app.controllers.v1.metrics import api as metrics_api, core_metrics_api, set_metrics_service


def create_app() -> Flask:
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Enable CORS
    CORS(app)
    
    # Root route - redirect to Swagger UI (register BEFORE API)
    @app.route('/')
    def index():
        return redirect('/swagger')
    
    # Favicon handler to avoid 404 errors
    @app.route('/favicon.ico')
    def favicon():
        return '', 204  # No content
    
    # Create Flask-RESTX API
    api = Api(
        app,
        title='S08 Metrics Service',
        version='1.0',
        description='Core Portal Metrics Service - Aggregates and provides metrics for the Core Portal',
        doc='/swagger',
        authorizations={
            'Bearer': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'JWT Bearer token. Format: "Bearer <token>"'
            }
        },
        security='Bearer',
    )
    
    # Register namespaces
    # H21.1 - /api/v1/metrics/users/total
    api.add_namespace(metrics_api, path='/api/v1/metrics')
    
    # H21.2-H21.5 - /api/v1/core/metrics/...
    api.add_namespace(core_metrics_api, path='/api/v1/core/metrics')
    
    return app


def create_metrics_service() -> MetricsService:
    """Create and configure the MetricsService"""
    return MetricsService(
        rabbitmq_url=os.getenv("RABBITMQ_URL"),
        s01_events_queue=os.getenv("S01_EVENTS_QUEUE", "s01_events_queue"),
        s04_events_queue=os.getenv("S04_EVENTS_QUEUE", "s04_events_queue"),
        s08_events_queue=os.getenv("S08_EVENTS_QUEUE", "s08_events_queue"),
        s08_s01_requests_queue=os.getenv("S08_S01_REQUESTS_QUEUE", "s08_s01_requests_queue"),
        s08_s01_responses_queue=os.getenv("S08_S01_RESPONSES_QUEUE", "s08_s01_responses_queue"),
        s08_s04_requests_queue=os.getenv("S08_S04_REQUESTS_QUEUE", "s08_s04_requests_queue"),
        s08_s04_responses_queue=os.getenv("S08_S04_RESPONSES_QUEUE", "s08_s04_responses_queue"),
        s08_s07_requests_queue=os.getenv("S08_S07_REQUESTS_QUEUE", "s08_s07_requests_queue"),
        s08_s07_responses_queue=os.getenv("S08_S07_RESPONSES_QUEUE", "s08_s07_responses_queue"),
        s14_s08_requests_queue=os.getenv("S14_S08_REQUESTS_QUEUE", "s14_s08_requests_queue"),
        s14_s08_responses_queue=os.getenv("S14_S08_RESPONSES_QUEUE", "s14_s08_responses_queue"),
    )


def main():
    """Main entry point"""
    print("=" * 60)
    print("S08 Metrics Service - Starting...")
    print("=" * 60)
    
    # Create metrics service
    metrics_service = create_metrics_service()
    
    # Set the service in the controller module
    set_metrics_service(metrics_service)
    
    # Start RabbitMQ consumers in background threads
    print("[Main] Starting MetricsService background workers...")
    metrics_service.start()
    
    # Create Flask app
    app = create_app()
    
    # Get HTTP port from environment
    http_port = int(os.getenv("HTTP_PORT", "5008"))
    
    # Run Flask server
    print(f"[Main] Starting HTTP server on port {http_port}...")
    print(f"[Main] Swagger UI available at: http://localhost:{http_port}/swagger")
    print("=" * 60)
    
    try:
        # Run Flask in production mode (use_reloader=False to avoid double initialization)
        app.run(
            host="0.0.0.0",
            port=http_port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
        metrics_service.stop()
    finally:
        print("[Main] Service stopped")


if __name__ == "__main__":
    main()
