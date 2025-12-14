from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import collections
from .collections import (
    employees_collection,
    roles_collection,
    keys_collection,
    login_attempts_collection
)

# Import services
from .services.AuthService import AuthService
from .services.EmployeeService import EmployeeService
from .services.RoleService import RoleService
from .utils.jwt_service import JWTService
from .utils.logger import Logger

# Import controllers
from .controllers.v1.core_auth import create_core_auth_blueprint
from .controllers.jwks import create_jwks_blueprint

def create_app():
    """
    Create and configure Flask application
    """
    app = Flask(__name__)
    CORS(app)
    
    # Initialize logger
    logger = Logger("CoreEmployeeIdentityService")
    
    # Initialize JWT service
    jwt_service = JWTService(keys_collection)
    
    # Initialize services
    auth_service = AuthService(
        employees_collection=employees_collection,
        roles_collection=roles_collection,
        login_attempts_collection=login_attempts_collection,
        jwt_service=jwt_service,
        logger=logger
    )
    
    employee_service = EmployeeService(
        employees_collection=employees_collection,
        roles_collection=roles_collection,
        logger=logger
    )
    
    role_service = RoleService(
        roles_collection=roles_collection,
        logger=logger
    )
    
    # Register blueprints
    app.register_blueprint(create_core_auth_blueprint(
        auth_service=auth_service,
        employee_service=employee_service,
        jwt_service=jwt_service,
        logger=logger
    ))
    
    app.register_blueprint(create_jwks_blueprint(jwt_service))
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health():
        return {"status": "ok", "service": "Core Employee Identity Service"}, 200
    
    return app

def main():
    """
    Main entry point
    """
    app = create_app()
    
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Core Employee Identity Service on {host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)

if __name__ == '__main__':
    main()
