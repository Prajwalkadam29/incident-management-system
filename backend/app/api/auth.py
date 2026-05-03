import structlog
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.core.security import verify_password, create_access_token, hash_password, get_current_user
from app.core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


# ── Pre-hash once at import time, not on every request ──
_USERS: dict = {}

def _build_user_store() -> dict:
    """
    Called once when the module loads.
    Bcrypt is intentionally slow — never call hash_password() in a request handler.
    """
    return {
        settings.ADMIN_USERNAME: {
            "hashed_password": hash_password(settings.ADMIN_PASSWORD),
            "role": "admin",
        },
        settings.VIEWER_USERNAME: {
            "hashed_password": hash_password(settings.VIEWER_PASSWORD),
            "role": "viewer",
        },
    }

# Build once on startup
_USERS = _build_user_store()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    user = _USERS.get(request.username)

    if not user or not verify_password(request.password, user["hashed_password"]):
        logger.warning("Failed login attempt", username=request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(data={
        "sub": request.username,
        "role": user["role"],
    })

    logger.info("User logged in", username=request.username, role=user["role"])

    return TokenResponse(
        access_token=token,
        username=request.username,
        role=user["role"],
    )


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user