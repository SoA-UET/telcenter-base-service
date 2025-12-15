"""
JWT Authentication Utilities for S07 Partner Management Service.

Implements JWKS-based JWT verification according to the specification:
- Fetches JWKS from Identity Service at startup and periodically (TTL-based)
- Verifies JWT signature with RS256 algorithm
- Validates JWT claims (exp, iat, sub, full_name, email, permissions)
"""

import os
import jwt
import threading
import time
import requests
from functools import wraps
from flask import request, jsonify, g
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


class JWKSManager:
    """
    Manages JWKS (JSON Web Key Set) fetching and caching.
    Thread-safe implementation with TTL-based refresh.
    """
    
    def __init__(self):
        self.identity_service_url = os.getenv('IDENTITY_SERVICE_URL', 'http://localhost:8000')
        self.ttl_minutes = int(os.getenv('JWKS_TTL_IN_MINUTES', '10'))
        self.keys: Dict[str, Dict[str, Any]] = {}  # kid -> key data
        self.lock = threading.RLock()
        self.last_fetch_time: Optional[float] = None
        self.refresh_thread: Optional[threading.Thread] = None
        self.running = False
    
    def start(self):
        """Start the JWKS manager - fetch keys and start refresh thread."""
        self._fetch_jwks()
        self.running = True
        self.refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self.refresh_thread.start()
    
    def stop(self):
        """Stop the JWKS manager."""
        self.running = False
    
    def _fetch_jwks(self):
        """Fetch JWKS from Identity Service."""
        try:
            url = f"{self.identity_service_url}/.well-known/jwks.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            jwks_data = response.json()
            
            with self.lock:
                # Handle both single key and array of keys
                if isinstance(jwks_data, list):
                    self.keys = {key['kid']: key for key in jwks_data}
                elif isinstance(jwks_data, dict):
                    if 'keys' in jwks_data:
                        # Standard JWKS format with 'keys' array
                        self.keys = {key['kid']: key for key in jwks_data['keys']}
                    elif 'kid' in jwks_data:
                        # Single key format
                        self.keys = {jwks_data['kid']: jwks_data}
                
                self.last_fetch_time = time.time()
            
            print(f"[JWKSManager] Successfully fetched {len(self.keys)} key(s)")
        except Exception as e:
            print(f"[JWKSManager] Failed to fetch JWKS: {e}")
            # Continue with cached keys (graceful degradation)
    
    def _refresh_loop(self):
        """Background thread for TTL-based JWKS refresh."""
        while self.running:
            time.sleep(self.ttl_minutes * 60)
            if self.running:
                self._fetch_jwks()
    
    def get_public_key(self, kid: str) -> Optional[str]:
        """Get public key by key ID (kid). Does NOT refresh on miss."""
        with self.lock:
            key_data = self.keys.get(kid)
            if key_data:
                return key_data.get('public_key')
            return None
    
    def get_key_data(self, kid: str) -> Optional[Dict[str, Any]]:
        """Get full key data by key ID (kid)."""
        with self.lock:
            return self.keys.get(kid)


# Global JWKS manager instance
_jwks_manager: Optional[JWKSManager] = None
_jwks_manager_lock = threading.Lock()


def get_jwks_manager() -> JWKSManager:
    """Get or create the global JWKS manager instance."""
    global _jwks_manager
    with _jwks_manager_lock:
        if _jwks_manager is None:
            _jwks_manager = JWKSManager()
            _jwks_manager.start()
        return _jwks_manager


def verify_jwt(token: str) -> Dict[str, Any]:
    """
    Verify a JWT token according to specification.
    
    Args:
        token: The JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        ValueError: If verification fails
    """
    manager = get_jwks_manager()
    
    # Step 1: Parse JWT Header
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError as e:
        raise ValueError(f"Invalid JWT format: {e}")
    
    alg = unverified_header.get('alg')
    kid = unverified_header.get('kid')
    
    # Reject if alg != RS256 or kid is missing
    if alg != 'RS256':
        raise ValueError(f"Unsupported algorithm: {alg}. Only RS256 is supported.")
    
    if not kid:
        raise ValueError("Missing 'kid' in JWT header")
    
    # Step 2: Resolve Public Key (DO NOT refresh JWKS on miss)
    public_key_pem = manager.get_public_key(kid)
    
    if not public_key_pem:
        raise ValueError(f"Unknown key ID: {kid}")
    
    # Step 3: Verify Signature
    try:
        payload = jwt.decode(
            token,
            public_key_pem,
            algorithms=['RS256'],
            options={
                'require': ['exp', 'iat', 'sub'],
                'verify_exp': True,
                'verify_iat': True,
            }
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidIssuedAtError:
        raise ValueError("Invalid 'iat' claim")
    except jwt.InvalidSignatureError:
        raise ValueError("Invalid token signature")
    except jwt.DecodeError as e:
        raise ValueError(f"Token decode error: {e}")
    
    # Step 4: Validate Claims
    required_claims = ['sub', 'full_name', 'email']
    for claim in required_claims:
        if claim not in payload:
            raise ValueError(f"Missing required claim: {claim}")
    
    # Ensure permissions is a list (default to empty list)
    if 'permissions' not in payload:
        payload['permissions'] = []
    elif not isinstance(payload['permissions'], list):
        raise ValueError("'permissions' claim must be an array")
    
    return payload


def jwt_required(f):
    """
    Decorator for protecting routes with JWT authentication.
    
    Usage:
        @api.route('/protected')
        class ProtectedResource(Resource):
            @jwt_required
            def get(self):
                # Access user info via g.current_user
                return {"user": g.current_user}
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if auth is disabled (for testing)
        if os.getenv('DISABLE_AUTH', 'false').lower() == 'true':
            g.current_user = {
                'sub': 'test-user',
                'full_name': 'Test User',
                'email': 'test@example.com',
                'permissions': [],
            }
            return f(*args, **kwargs)
        
        # Get Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header:
            return {
                "status": "error",
                "message": "Missing Authorization header"
            }, 401
        
        # Extract token from "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return {
                "status": "error",
                "message": "Invalid Authorization header format. Expected: Bearer <token>"
            }, 401
        
        token = parts[1]
        
        try:
            # Verify and decode JWT
            payload = verify_jwt(token)
            
            # Store user info in Flask's g object
            g.current_user = {
                'sub': payload.get('sub'),
                'full_name': payload.get('full_name'),
                'email': payload.get('email'),
                'permissions': payload.get('permissions', []),
            }
            
            return f(*args, **kwargs)
        
        except ValueError as e:
            print(f"[Auth] JWT verification failed: {e}")
            return {
                "status": "error",
                "message": "Unauthorized"
            }, 401
    
    return decorated


def require_permission(permission: str):
    """
    Decorator factory for checking specific permission.
    Must be used after @jwt_required.
    
    Usage:
        @api.route('/admin')
        class AdminResource(Resource):
            @jwt_required
            @require_permission('admin:write')
            def post(self):
                return {"status": "ok"}
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            current_user = getattr(g, 'current_user', None)
            if not current_user:
                return {
                    "status": "error",
                    "message": "Unauthorized"
                }, 401
            
            permissions = current_user.get('permissions', [])
            if permission not in permissions:
                return {
                    "status": "error",
                    "message": "Forbidden - insufficient permissions"
                }, 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator
