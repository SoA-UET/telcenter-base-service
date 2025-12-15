"""
JWT Authentication Utilities for S08 Metrics Service.

Implements JWKS-based JWT verification according to the specification in VERIFY.md.
"""

import os
import time
import threading
import json
import base64
from typing import Optional
from functools import wraps
from datetime import datetime

import requests
from flask import request, jsonify, g


class JWKSManager:
    """
    Manages JWKS (JSON Web Key Set) fetching and caching.
    
    Fetches public keys from the Identity Service at startup and on a TTL schedule.
    Keys are cached in memory and used for JWT verification.
    """
    
    def __init__(
        self,
        identity_service_url: str | None = None,
        jwks_ttl_minutes: int | None = None
    ):
        self.identity_service_url = identity_service_url or os.getenv("IDENTITY_SERVICE_URL", "http://localhost:5004")
        self.jwks_ttl_minutes = jwks_ttl_minutes or int(os.getenv("JWKS_TTL_IN_MINUTES", "10"))
        
        self.keys: dict[str, dict] = {}  # kid -> key data
        self.last_refresh: float = 0
        self.lock = threading.RLock()
        
        # Fetch keys at startup
        self._refresh_keys()
        
        # Start background refresh thread
        self._start_refresh_thread()
    
    def _get_jwks_url(self) -> str:
        """Get the JWKS endpoint URL"""
        return f"{self.identity_service_url}/.well-known/jwks.json"
    
    def _refresh_keys(self):
        """Fetch and cache JWKS from Identity Service"""
        try:
            url = self._get_jwks_url()
            print(f"[JWKSManager] Fetching JWKS from {url}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            jwks = response.json()
            
            with self.lock:
                # Handle both single key and array of keys
                if isinstance(jwks, list):
                    self.keys = {key["kid"]: key for key in jwks}
                elif isinstance(jwks, dict):
                    if "keys" in jwks:
                        self.keys = {key["kid"]: key for key in jwks["keys"]}
                    else:
                        self.keys = {jwks["kid"]: jwks}
                
                self.last_refresh = time.time()
            
            print(f"[JWKSManager] Cached {len(self.keys)} keys")
            
        except requests.exceptions.RequestException as e:
            print(f"[JWKSManager] Warning: Failed to fetch JWKS: {e}")
            # Continue using cached keys (graceful degradation)
        except Exception as e:
            print(f"[JWKSManager] Warning: Error processing JWKS: {e}")
    
    def _start_refresh_thread(self):
        """Start background thread to refresh keys on TTL schedule"""
        def refresh_loop():
            while True:
                time.sleep(self.jwks_ttl_minutes * 60)
                self._refresh_keys()
        
        thread = threading.Thread(target=refresh_loop, daemon=True, name="JWKSRefresh")
        thread.start()
    
    def get_key(self, kid: str) -> dict | None:
        """
        Get public key by key ID.
        
        Note: MUST NOT refresh JWKS on unknown kid (DoS prevention).
        """
        with self.lock:
            return self.keys.get(kid)


class JWTVerifier:
    """
    Verifies JWT tokens according to the specification.
    
    Verification steps:
    1. Parse JWT header - check alg is RS256, kid exists
    2. Resolve public key from cached JWKS
    3. Verify signature
    4. Validate claims (exp, iat, sub, email, full_name)
    """
    
    ALLOWED_ALGORITHMS = ["RS256"]
    CLOCK_SKEW_SECONDS = 60  # Allow 60 seconds clock skew for iat
    
    def __init__(self, jwks_manager: JWKSManager):
        self.jwks_manager = jwks_manager
    
    def verify_token(self, token: str) -> dict | None:
        """
        Verify JWT token and return decoded payload if valid.
        
        Returns:
            Decoded payload dict if valid, None if invalid.
        """
        try:
            # Split token into parts
            parts = token.split(".")
            if len(parts) != 3:
                print("[JWTVerifier] Invalid token format: expected 3 parts")
                return None
            
            header_b64, payload_b64, signature_b64 = parts
            
            # Step 1: Parse and validate header
            header = self._decode_part(header_b64)
            if not header:
                print("[JWTVerifier] Failed to decode header")
                return None
            
            alg = header.get("alg")
            kid = header.get("kid")
            
            if alg not in self.ALLOWED_ALGORITHMS:
                print(f"[JWTVerifier] Invalid algorithm: {alg}")
                return None
            
            if not kid:
                print("[JWTVerifier] Missing kid in header")
                return None
            
            # Step 2: Resolve public key (DO NOT refresh on unknown kid)
            key_data = self.jwks_manager.get_key(kid)
            if not key_data:
                print(f"[JWTVerifier] Unknown kid: {kid}")
                return None
            
            # Step 3: Verify signature
            public_key_pem = key_data.get("public_key")
            if not public_key_pem:
                print("[JWTVerifier] No public_key in JWKS")
                return None
            
            if not self._verify_signature(header_b64, payload_b64, signature_b64, public_key_pem):
                print("[JWTVerifier] Signature verification failed")
                return None
            
            # Step 4: Validate claims
            payload = self._decode_part(payload_b64)
            if not payload:
                print("[JWTVerifier] Failed to decode payload")
                return None
            
            if not self._validate_claims(payload):
                return None
            
            return payload
            
        except Exception as e:
            print(f"[JWTVerifier] Error verifying token: {e}")
            return None
    
    def _decode_part(self, b64_str: str) -> dict | None:
        """Decode base64url encoded JWT part"""
        try:
            # Add padding if needed
            padding = 4 - len(b64_str) % 4
            if padding != 4:
                b64_str += "=" * padding
            
            # Replace URL-safe chars
            b64_str = b64_str.replace("-", "+").replace("_", "/")
            
            decoded = base64.b64decode(b64_str)
            return json.loads(decoded)
        except Exception as e:
            print(f"[JWTVerifier] Error decoding: {e}")
            return None
    
    def _verify_signature(
        self,
        header_b64: str,
        payload_b64: str,
        signature_b64: str,
        public_key_pem: str
    ) -> bool:
        """Verify JWT signature using RS256"""
        try:
            # Import cryptography here to handle optional dependency
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend
            from cryptography.exceptions import InvalidSignature
            
            # Load public key
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode(),
                backend=default_backend()
            )
            
            # Decode signature
            sig_padding = 4 - len(signature_b64) % 4
            if sig_padding != 4:
                signature_b64 += "=" * sig_padding
            signature_b64 = signature_b64.replace("-", "+").replace("_", "/")
            signature = base64.b64decode(signature_b64)
            
            # Message to verify
            message = f"{header_b64}.{payload_b64}".encode()
            
            # Verify signature
            public_key.verify(
                signature,
                message,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            
            return True
            
        except InvalidSignature:
            return False
        except Exception as e:
            print(f"[JWTVerifier] Error verifying signature: {e}")
            return False
    
    def _validate_claims(self, payload: dict) -> bool:
        """Validate JWT claims"""
        now = time.time()
        
        # Check exp (must not be expired)
        exp = payload.get("exp")
        if not exp or now > exp:
            print("[JWTVerifier] Token expired")
            return False
        
        # Check iat (must be within acceptable skew)
        iat = payload.get("iat")
        if not iat or iat > now + self.CLOCK_SKEW_SECONDS:
            print("[JWTVerifier] Invalid iat claim")
            return False
        
        # Check sub (user ID must exist)
        sub = payload.get("sub")
        if not sub:
            print("[JWTVerifier] Missing sub claim")
            return False
        
        # full_name and email should exist
        if "full_name" not in payload:
            print("[JWTVerifier] Missing full_name claim")
            return False
        
        if "email" not in payload:
            print("[JWTVerifier] Missing email claim")
            return False
        
        return True


# Global instances
_jwks_manager: JWKSManager | None = None
_jwt_verifier: JWTVerifier | None = None


def get_jwt_verifier() -> JWTVerifier:
    """Get or create JWT verifier singleton"""
    global _jwks_manager, _jwt_verifier
    
    if _jwt_verifier is None:
        _jwks_manager = JWKSManager()
        _jwt_verifier = JWTVerifier(_jwks_manager)
    
    return _jwt_verifier


def jwt_required(f):
    """
    Decorator to require JWT authentication on an endpoint.
    
    Extracts JWT from Authorization header, verifies it, and stores
    the decoded payload in Flask's g object as g.jwt_payload.
    
    Returns HTTP 401 if authentication fails.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Authentication token is invalid or expired"
            }), 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Verify token
        verifier = get_jwt_verifier()
        payload = verifier.verify_token(token)
        
        if payload is None:
            return jsonify({
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Authentication token is invalid or expired"
            }), 401
        
        # Store payload in g for use in endpoint
        g.jwt_payload = payload
        g.user_id = payload.get("sub")
        g.user_email = payload.get("email")
        g.user_name = payload.get("full_name")
        g.permissions = payload.get("permissions", [])
        
        return f(*args, **kwargs)
    
    return decorated


def check_permission(permission: str):
    """
    Decorator to check if user has a specific permission.
    Must be used after @jwt_required.
    
    Returns HTTP 403 if permission check fails.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            permissions = getattr(g, "permissions", [])
            
            if permission not in permissions:
                return jsonify({
                    "status": "error",
                    "error_code": "FORBIDDEN",
                    "message": "User does not have permission to view metrics"
                }), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator
