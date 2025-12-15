#!/usr/bin/env python3
"""
Telcenter Base Service - Main Entry Point

This is the main entry point for the Telcenter microservices.
It initializes and starts the various services.
"""

import os
from flask import Flask
from flask_restx import Api

# Import services
from app.services.s05_knowledge_validator_service import KnowledgeValidatorService

# Import controllers
from app.controllers.v1 import partner_updates


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Configure Flask
    app.config['RESTX_MASK_SWAGGER'] = False
    app.config['RESTX_VALIDATE'] = True
    
    # Create API with Swagger documentation
    api = Api(
        app,
        version='1.0',
        title='Telcenter Core API',
        description='API for Telcenter Core Services',
        doc='/api/docs',
        authorizations={
            'Bearer Auth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'Type in the *\'Value\'* input box below: **\'Bearer &lt;JWT&gt;\'**, where JWT is the token'
            }
        }
    )
    
    # Initialize S05 Knowledge Validator Service
    print("[Main] Initializing S05 Knowledge Validator Service...")
    s05_service = KnowledgeValidatorService()
    
    # Inject service into controllers
    partner_updates.set_service(s05_service)
    
    # Register API namespaces
    api.add_namespace(partner_updates.api, path='/api/v1/partner-updates')
    
    print("[Main] All services initialized successfully")
    
    # Store service reference for cleanup
    app.s05_service = s05_service
    
    return app


def main():
    """Main function to start the application"""
    print("=" * 60)
    print("Telcenter Core - Starting Services")
    print("=" * 60)
    
    # Create Flask app
    app = create_app()
    
    # Get configuration from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5005))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"\n[Main] Starting Flask server on {host}:{port}")
    print(f"[Main] Debug mode: {debug}")
    print(f"[Main] API Documentation: http://{host}:{port}/api/docs")
    print("=" * 60)
    
    try:
        # Start Flask application
        app.run(host=host, port=port, debug=debug, threaded=True)
    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
    finally:
        # Cleanup services
        if hasattr(app, 's05_service'):
            app.s05_service.close()
        print("[Main] Cleanup complete")


if __name__ == '__main__':
    main()
