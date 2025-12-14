from flask import Blueprint, jsonify
from ..utils.jwt_service import JWTService

def create_jwks_blueprint(jwt_service: JWTService):
    """
    Create blueprint for JWKS endpoint
    """
    blueprint = Blueprint('jwks', __name__)
    
    @blueprint.route('/.well-known/jwks.json', methods=['GET'])
    def get_jwks():
        """
        Get JWKS (JSON Web Key Set) containing all active public keys
        """
        jwks = jwt_service.get_jwks()
        return jsonify(jwks), 200
    
    return blueprint
