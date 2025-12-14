import os
from dotenv import load_dotenv
from flask import Flask
from flask_restx import Api
from flask_cors import CORS

# Load environment variables
load_dotenv()

# Import services
from .services.LoggingService import LoggingService
from .services.JWTService import JWTService
from .services.CustomerIdentityService import CustomerIdentityService
from .services.MessageQueueService import MessageQueueService

# Import collections
from .collections.customers import CustomersCollection

# Import controllers
from .controllers.v1 import auth
import json
import threading

def create_app():
    """Create and configure the Flask application"""
    
    # Initialize Flask app
    app = Flask(__name__)
    CORS(app)
    
    # Flask configuration
    app.config['RESTX_MASK_SWAGGER'] = False
    app.config['ERROR_404_HELP'] = False
    
    # Initialize API
    api = Api(
        app,
        version='1.0',
        title='Telcenter Customer Identity Service (S04)',
        description='Authentication and identity management for Telcenter customers',
        doc='/docs'
    )
    
    # Initialize logging service
    logging_service = LoggingService("S04_CustomerIdentityService")
    logging_service.log_info("Starting Customer Identity Service")
    
    # Initialize MongoDB collection
    customers_collection = CustomersCollection()
    logging_service.log_info("MongoDB connection established")
    
    # Initialize JWT service
    jwt_service = JWTService(logging_service)
    
    # Initialize Customer Identity service
    customer_identity_service = CustomerIdentityService(
        customers_collection, 
        logging_service,
        jwt_service
    )
    
    # Initialize MessageQueueService for RabbitMQ communication
    message_queue_service = MessageQueueService()
    
    # Start RabbitMQ request consumer thread for A04b API
    def handle_rabbitmq_requests():
        """Handle incoming RabbitMQ requests from S08"""
        request_queue = os.getenv("S08_S04_REQUESTS_QUEUE", "s08_s04_requests_queue")
        response_queue = os.getenv("S08_S04_RESPONSES_QUEUE", "s08_s04_responses_queue")
        
        def callback(message):
            """Process RabbitMQ request"""
            try:
                method = message.get("method")
                request_id = message.get("id")
                
                logging_service.log_info(f"Received RabbitMQ request: {method}", {"id": request_id})
                
                if method == "get_customers_count":
                    try:
                        count = customer_identity_service.get_customers_count()
                        response = {
                            "id": request_id,
                            "result": {
                                "status": "success",
                                "content": count
                            }
                        }
                    except Exception as e:
                        response = {
                            "id": request_id,
                            "result": {
                                "status": "error",
                                "content": str(e)
                            }
                        }
                    
                    # Send response
                    message_queue_service.publish(response_queue, response)
                    logging_service.log_info(f"Sent RabbitMQ response", {"id": request_id})
                else:
                    logging_service.log_warning(f"Unknown RabbitMQ method: {method}")
                    
            except Exception as e:
                logging_service.log_error(f"Error handling RabbitMQ request: {str(e)}")
        
        message_queue_service.consume(request_queue, callback)
    
    # Start RabbitMQ consumer in a separate thread
    rabbitmq_thread = threading.Thread(target=handle_rabbitmq_requests, daemon=True)
    rabbitmq_thread.start()
    logging_service.log_info("RabbitMQ consumer thread started")
    
    # Inject dependencies into controller
    auth.init_dependencies(
        customer_identity_service,
        jwt_service,
        message_queue_service,
        logging_service
    )
    
    # Register API namespaces
    api.add_namespace(auth.api, path='/api/v1/auth')
    
    # Add JWKS endpoint at root level (not under /api/v1/auth)
    @app.route('/.well-known/jwks.json')
    def jwks():
        """JWKS endpoint for public key distribution"""
        jwks_data = jwt_service.get_jwks()
        return jwks_data, 200
    
    # Add health check endpoint
    @app.route('/health')
    def health():
        """Health check endpoint"""
        return {"status": "healthy", "service": "S04_CustomerIdentityService"}, 200
    
    # Serve test HTML interface
    @app.route('/')
    def index():
        """Serve test interface"""
        from flask import send_from_directory
        return send_from_directory('static', 'index.html')
    
    logging_service.log_info("Application initialized successfully")
    
    return app

def main():
    """Main entry point"""
    app = create_app()
    
    # Get Flask configuration from environment
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    
    print(f"""
    ╔════════════════════════════════════════════════════════════╗
    ║  Telcenter Customer Identity Service (S04)                ║
    ║  Running on http://{host}:{port}                   ║
    ║  API Documentation: http://{host}:{port}/docs      ║
    ║  Health Check: http://{host}:{port}/health         ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    app.run(host=host, port=port, debug=debug, use_reloader=False)

if __name__ == "__main__":
    main()
