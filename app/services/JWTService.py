import os
import jwt
import uuid
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from typing import Dict, List, Optional
from .LoggingService import LoggingService

class JWTService:
    """
    Service for JWT signing and verification using RS256 algorithm.
    Manages RSA key pairs and provides JWKS endpoint data.
    """
    
    def __init__(self, logging_service: LoggingService):
        self.logging_service = logging_service
        self.keys: List[Dict] = []
        self.jwt_expiration_minutes = int(os.getenv("JWT_EXPIRATION_TIME_IN_MINUTES", "10"))
        
        # Generate initial key pair
        self._generate_new_key_pair()
        self.logging_service.log_info("JWTService initialized with new key pair")
    
    def _generate_new_key_pair(self):
        """Generate a new RSA key pair"""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Get public key
        public_key = private_key.public_key()
        
        # Serialize private key to PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        # Serialize public key to PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Generate unique key ID
        kid = str(uuid.uuid4())
        
        # Store key pair information
        key_info = {
            "kid": kid,
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "private_key": private_pem,
            "public_key": public_pem,
            "created_at": datetime.now()
        }
        
        self.keys.append(key_info)
        self.logging_service.log_info(f"Generated new RSA key pair", {"kid": kid})
    
    def _get_latest_key(self) -> Dict:
        """Get the latest active key pair"""
        if not self.keys:
            self._generate_new_key_pair()
        return self.keys[-1]
    
    def sign_token(self, customer_id: str, full_name: str, email: str = None) -> str:
        """
        Sign a JWT token for a customer.
        Note: Customer Identity service doesn't include 'permissions' in JWT.
        
        Args:
            customer_id: The customer's unique identifier
            full_name: The customer's full name
            email: The customer's email (optional, from OAuth)
        
        Returns:
            Signed JWT token string
        """
        latest_key = self._get_latest_key()
        
        now = datetime.utcnow()
        expiration = now + timedelta(minutes=self.jwt_expiration_minutes)
        
        payload = {
            "sub": customer_id,
            "full_name": full_name,
            "iat": int(now.timestamp()),
            "exp": int(expiration.timestamp())
        }
        
        # Add email if provided (from OAuth)
        if email:
            payload["email"] = email
        
        token = jwt.encode(
            payload,
            latest_key["private_key"],
            algorithm="RS256",
            headers={"kid": latest_key["kid"]}
        )
        
        self.logging_service.log_audit(
            "JWT_TOKEN_ISSUED",
            customer_id,
            {"kid": latest_key["kid"], "exp": expiration.isoformat()}
        )
        
        return token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify a JWT token using the stored public keys.
        
        Args:
            token: The JWT token string to verify
        
        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            # Decode header to get kid
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                self.logging_service.log_warning("Token missing kid in header")
                return None
            
            # Find the key with matching kid
            key_info = None
            for key in self.keys:
                if key["kid"] == kid:
                    key_info = key
                    break
            
            if not key_info:
                self.logging_service.log_warning(f"No key found for kid: {kid}")
                return None
            
            # Verify and decode token
            payload = jwt.decode(
                token,
                key_info["public_key"],
                algorithms=["RS256"]
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            self.logging_service.log_warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            self.logging_service.log_warning(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            self.logging_service.log_error(f"Error verifying token: {str(e)}")
            return None
    
    def get_jwks(self) -> List[Dict]:
        """
        Get JWKS (JSON Web Key Set) for public key distribution.
        Returns all currently active public keys.
        
        Returns:
            List of public key information
        """
        jwks = []
        for key in self.keys:
            jwks.append({
                "kid": key["kid"],
                "kty": key["kty"],
                "alg": key["alg"],
                "use": key["use"],
                "public_key": key["public_key"]
            })
        
        return jwks
