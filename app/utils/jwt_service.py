import jwt
import uuid
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from pymongo.collection import Collection
from typing import Any
import os

class JWTService:
    """
    Service for signing and verifying JWTs using RS256 algorithm
    """
    
    def __init__(self, keys_collection: Collection):
        self.keys_collection = keys_collection
        self.jwt_expiration_minutes = int(os.getenv('JWT_EXPIRATION_TIME_IN_MINUTES', '10'))
        
    def _get_latest_key(self):
        """Get the latest active key pair"""
        keys = list(self.keys_collection.find({"use": "sig"}).sort("created_at", -1).limit(1))
        
        if not keys:
            # Generate a new key pair if none exists
            return self._generate_key_pair()
        
        return keys[0]
    
    def _generate_key_pair(self):
        """Generate a new RSA key pair"""
        # Generate RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Get private key in PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        # Get public key in PEM format
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Create key document
        kid = str(uuid.uuid4())
        key_doc = {
            "kid": kid,
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "private_key": private_pem,
            "public_key": public_pem,
            "created_at": datetime.now()
        }
        
        self.keys_collection.insert_one(key_doc)
        return key_doc
    
    def sign_token(self, payload: dict[str, Any]) -> str:
        """
        Sign a JWT token using the latest key pair
        
        Args:
            payload: JWT payload containing user information
            
        Returns:
            Signed JWT token
        """
        key_doc = self._get_latest_key()
        
        # Add standard claims
        now = datetime.now()
        payload_with_claims = {
            **payload,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self.jwt_expiration_minutes)).timestamp())
        }
        
        # Sign the token
        token = jwt.encode(
            payload_with_claims,
            key_doc["private_key"],
            algorithm="RS256",
            headers={"kid": key_doc["kid"]}
        )
        
        return token
    
    def get_jwks(self) -> list[dict]:
        """
        Get all active public keys in JWKS format
        
        Returns:
            List of JWKS key objects
        """
        keys = list(self.keys_collection.find({"use": "sig"}))
        
        jwks = []
        for key in keys:
            jwks.append({
                "kid": key["kid"],
                "kty": key["kty"],
                "alg": key["alg"],
                "use": key["use"],
                "public_key": key["public_key"]
            })
        
        return jwks
    
    def verify_token(self, token: str) -> dict[str, Any]:
        """
        Verify and decode a JWT token
        
        Args:
            token: JWT token to verify
            
        Returns:
            Decoded payload if verification succeeds
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        # Decode header to get kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise jwt.InvalidTokenError("Token missing kid in header")
        
        # Get the key from database
        key_doc = self.keys_collection.find_one({"kid": kid, "use": "sig"})
        
        if not key_doc:
            raise jwt.InvalidTokenError(f"Key with kid {kid} not found")
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            key_doc["public_key"],
            algorithms=["RS256"]
        )
        
        return payload
