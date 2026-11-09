import hashlib
import secrets
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.app.core.config import settings

security = HTTPBearer(auto_error=False)

def verify_pin(input_pin: str) -> bool:
    if not settings.DASHBOARD_PIN:
        return True
    return secrets.compare_digest(input_pin.strip(), settings.DASHBOARD_PIN.strip())

def mask_secret(secret: str | None) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "••••••••"
    return secret[:4] + "••••••••" + secret[-4:]
