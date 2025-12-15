"""
JWT Authentication utilities for Partner Portal APIs.

Implements JWKS-based JWT verification according to the VERIFY.md specification.
"""

import os
import time
import threading
import functools
from typing import Optional, Callable
import requests
import jwt
from flask import request, jsonify, g


class JWKSManager:
    """
    Manages JWKS fetching and caching for JWT verification.
    """
    
    def __init__(self):
        self.identity_service_url = os.getenv("IDENTITY_SERVICE_URL", "http://localhost:5000")
        self.jwks_ttl_minutes = int(os.getenv("JWKS_TTL_IN_MINUTES", "10"))
        
        self.jwks_cache: dict = {}
        self.jwks_last_fetched: Optional[float] = None
        self.jwks_lock = threading.Lock()
        
        # Start background refresh thread
        self._start_refresh_thread()
    
    def _start_refresh_thread(self):
        """
        Start a background thread to refresh JWKS on TTL schedule.
        """
        def refresh_loop():
            while True:
                try:
                    self._fetch_jwks()
                except Exception as e:
                    print(f"[JWKSManager] Failed to refresh JWKS: {e}")
                
                # Sleep for TTL duration
                time.sleep(self.jwks_ttl_minutes * 60)
        
        thread = threading.Thread(target=refresh_loop, daemon=True)
        thread.start()
    
    def _fetch_jwks(self):
        """
        Fetch JWKS from Identity Service.
        """
        jwks_url = f"{self.identity_service_url}/.well-known/jwks.json"
        
        try:
            response = requests.get(jwks_url, timeout=10)
            response.raise_for_status()
            
            jwks_data = response.json()
            
            with self.jwks_lock:
                # Handle both single key and array of keys
                if isinstance(jwks_data, list):
                    for key_data in jwks_data:
                        kid = key_data.get("kid")
                        if kid:
                            self.jwks_cache[kid] = key_data
                else:
                    kid = jwks_data.get("kid")
                    if kid:
                        self.jwks_cache[kid] = jwks_data
                
                self.jwks_last_fetched = time.time()
            
            print(f"[JWKSManager] JWKS fetched successfully, {len(self.jwks_cache)} keys cached")
            
        except Exception as e:
            print(f"[JWKSManager] Error fetching JWKS: {e}")
            # Continue using cached keys (graceful degradation)
    
    def get_public_key(self, kid: str) -> Optional[str]:
        """
        Get public key by key ID from cache.
        DO NOT refresh on unknown kid (per VERIFY.md spec).
        """
        with self.jwks_lock:
            key_data = self.jwks_cache.get(kid)
            if key_data:
                return key_data.get("public_key")
            return None
    
    def initial_fetch(self):
        """
        Perform initial JWKS fetch at service startup.
        """
        self._fetch_jwks()


# Global JWKS manager instance
_jwks_manager: Optional[JWKSManager] = None


def get_jwks_manager() -> JWKSManager:
    """
    Get the global JWKS manager instance.
    """
    global _jwks_manager
    if _jwks_manager is None:
        _jwks_manager = JWKSManager()
        _jwks_manager.initial_fetch()
    return _jwks_manager


def verify_jwt_token(token: str) -> tuple[bool, Optional[dict], Optional[str]]:
    """
    Verify a JWT token according to VERIFY.md specification.
    
    Returns:
        tuple: (is_valid, payload, error_message)
    """
    try:
        # Step 1: Parse JWT Header
        unverified_header = jwt.get_unverified_header(token)
        
        alg = unverified_header.get("alg")
        kid = unverified_header.get("kid")
        
        # Reject if alg != RS256 or kid is missing
        if alg != "RS256":
            return False, None, "Invalid algorithm"
        
        if not kid:
            return False, None, "Missing kid in token header"
        
        # Step 2: Resolve Public Key (DO NOT refresh on unknown kid)
        jwks_manager = get_jwks_manager()
        public_key = jwks_manager.get_public_key(kid)
        
        if not public_key:
            return False, None, "Unknown key ID"
        
        # Step 3: Verify Signature
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"require": ["exp", "iat", "sub"]}
        )
        
        # Step 4: Validate Claims
        # exp and iat are validated by jwt.decode
        # Validate required claims exist
        if "sub" not in payload:
            return False, None, "Missing sub claim"
        
        if "full_name" not in payload:
            return False, None, "Missing full_name claim"
        
        if "email" not in payload:
            return False, None, "Missing email claim"
        
        # permissions is optional, default to empty array
        if "permissions" not in payload:
            payload["permissions"] = []
        elif not isinstance(payload["permissions"], list):
            return False, None, "permissions must be an array"
        
        return True, payload, None
        
    except jwt.ExpiredSignatureError:
        return False, None, "Token has expired"
    except jwt.InvalidTokenError as e:
        return False, None, f"Invalid token: {str(e)}"
    except Exception as e:
        return False, None, f"Token verification failed: {str(e)}"


def jwt_required(f: Callable) -> Callable:
    """
    Decorator to require JWT authentication on Flask routes.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        # Get Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return jsonify({
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Missing Authorization header"
            }), 401
        
        # Parse Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Invalid Authorization header format"
            }), 401
        
        token = parts[1]
        
        # Verify token
        is_valid, payload, error = verify_jwt_token(token)
        
        if not is_valid:
            return jsonify({
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": f"Authentication token is invalid or expired"
            }), 401
        
        # Store user info in Flask g object for use in route handler
        g.user_id = payload.get("sub")
        g.user_full_name = payload.get("full_name")
        g.user_email = payload.get("email")
        g.user_permissions = payload.get("permissions", [])
        
        return f(*args, **kwargs)
    
    return decorated


def permission_required(permission: str) -> Callable:
    """
    Decorator to require a specific permission.
    Must be used after @jwt_required.
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            permissions = getattr(g, "user_permissions", [])
            
            if permission not in permissions:
                return jsonify({
                    "status": "error",
                    "error_code": "FORBIDDEN",
                    "message": "User does not have permission to view metrics"
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator
