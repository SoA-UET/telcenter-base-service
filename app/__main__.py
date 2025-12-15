"""
S07 Partner Management Service - Entry Point

This service provides:
- HTTP APIs (H24, H11) via Flask
- RabbitMQ APIs (A07, A09a, A37) via MessageQueueService

The service runs:
1. Flask HTTP server in the main thread
2. RabbitMQ consumers in background daemon threads
"""

import os
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def start_amqp_server():
    """Start the AMQP server for RabbitMQ-based APIs."""
    try:
        from .services import partner_service
        from .services.MessageQueueService import MessageQueueService
        from .amqp import AMQPServer
        
        # Set up MessageQueueService for partner_service (for A09b events)
        mq_service = MessageQueueService()
        partner_service.set_mq_service(mq_service)
        
        # Create and start AMQP server
        amqp_server = AMQPServer(partner_service)
        amqp_server.start()
        
        print("[Main] AMQP server started successfully")
        return amqp_server
    except Exception as e:
        print(f"[Main] Failed to start AMQP server: {e}")
        return None


def start_http_server():
    """Start the Flask HTTP server."""
    from . import app, socketio
    
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"[Main] Starting HTTP server on {host}:{port}")
    
    # Use socketio.run for WebSocket support
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


def main():
    """Main entry point for S07 Partner Management Service."""
    print("=" * 60)
    print("S07 Partner Management Service")
    print("=" * 60)
    
    # Initialize JWKS manager for JWT authentication
    try:
        from .utils.auth import get_jwks_manager
        jwks_manager = get_jwks_manager()
        print("[Main] JWKS manager initialized")
    except Exception as e:
        print(f"[Main] Warning: Failed to initialize JWKS manager: {e}")
        print("[Main] JWT authentication may not work properly")
    
    # Start AMQP server (RabbitMQ consumers) in background threads
    amqp_server = start_amqp_server()
    
    # Start HTTP server (Flask) - this blocks
    start_http_server()


if __name__ == "__main__":
    main()
