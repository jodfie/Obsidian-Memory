---
title: JWT Authentication Implementation
type: decision
project: api-service
permalink: jwt-auth-implementation
created: 2025-01-15T10:30:00Z
updated: 2025-01-16T14:20:00Z
tags:
  - security
  - backend
  - architecture
supersedes: session-auth
custom_metadata:
  author: john.doe
  reviewers:
    - alice
    - bob
---

# JWT Authentication Implementation

## Context

We needed to choose between session-based and token-based authentication for our microservices architecture.

- [decision] Chose JWT over session cookies for stateless API #architecture
- [reason] Horizontal scaling without shared session store #scalability
- [tradeoff] Tokens can't be revoked without blacklist #security

## Implementation Details

- [implementation] Using RS256 with rotating keys #security (weekly rotation)
- [gotcha] Token refresh needs Redis for blacklist #infrastructure
- [pattern] Middleware validates on every request #performance
- [tip] Set short expiry (15min) with refresh tokens #security

```python
# Example JWT validation middleware
def validate_jwt(token: str) -> dict:
    """Validate JWT token and return payload."""
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=['RS256'])
        if is_blacklisted(payload['jti']):
            raise InvalidToken("Token has been revoked")
        return payload
    except jwt.ExpiredSignatureError:
        raise InvalidToken("Token expired")
```

- [fact] JWT is industry standard for stateless auth #standards
- [resource] https://jwt.io for testing tokens

## Relations

- depends_on [[infrastructure/redis-setup]]
- enables [[api-gateway/auth-middleware]]
- learned_from [[sessions/session-scaling-issues]]
- related_to [[security/user-authentication]]
- supersedes [[sessions/cookie-auth]]

## Testing

- [experiment] Tried session cookies first, didn't scale #experiment
- [solution] Use refresh tokens for long-lived sessions #workaround

See also [[security/OAuth Integration#Token Validation]] for related patterns.

## References

Link to [[API Documentation|our API docs]] and [[infrastructure/Redis Setup#^block-123|this specific config]].
