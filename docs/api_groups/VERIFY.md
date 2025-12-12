# This prompt below is used for services that have to use identity service 
## JWT Verification (JWKS-Based)

Every downstream service that consumes customer JWTs must implement JWKS-based verification.

### 1. JWKS Fetching

- Do not hard-code any public key.
- Fetch JWKS from Identity Service:

      {IDENTITY_SERVICE_URL}/.well-known/jwks.json

### 2. JWKS Caching Strategy

- Cache the JWKS document for **5–10 minutes**.
- For every incoming request:
  - Read the JWT header and extract `kid`.
  - Look up the matching key in the cached JWKS.
  - If the key is not found:
    - Refresh JWKS immediately.
    - Retry verification once.

### 3. Verification Logic

Downstream services must validate:

  - Signature:
      - Must use the public key matching `kid`.
      - Must use algorithm **RS256** only.

  - Claims:
      - `iss` is trusted.
      - `aud` matches the service.
      - `exp` is not expired.
      - `iat` is within a reasonable time window.
      - `nbf` is valid if present.
      - `sub` exists.

### 4. Behavior on Key Rotation

If the Identity Service rotates keys:

- Old tokens signed with the old `kid` must still verify because:
  - The old public key remains published in JWKS for the token lifetime.
- Once the old public key is removed:
  - Expired tokens will naturally be rejected.
- Downstream services must automatically refresh JWKS when a signature mismatch occurs.

### 5. Failure Handling

If the JWKS endpoint is temporarily unavailable:

- Continue using the cached JWKS (**graceful degradation**).
- Log warnings.
- Deny authentication only when:
  - Signature is invalid **and**
  - JWKS refresh fails.

### 6. Required Deliverables (per Downstream Service)

Each downstream service must provide:

- Authentication middleware/filter.
- JWKS provider with caching.
- Retry mechanism for signature verification.
- Monitoring for:
  - JWKS refresh events.
  - Key mismatch errors.
  - Suspicious or malformed tokens.
