from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db, settings
from app.models.user import User
from app.schemas.user import LoginRequest, TokenResponse, UserResponse
from app.security import verify_password, create_access_token
from app.api.deps import get_current_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


async def get_login_credentials(request: Request) -> tuple[str, str]:
    """
    Extract username/email and password from either form-encoded (OAuth2 / Swagger UI)
    or JSON payloads.
    """
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("JSON body must be an object.")
            username = str(body.get("username", ""))
            password = str(body.get("password", ""))
            return username, password
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid JSON payload format.",
            )
    else:
        try:
            form = await request.form()
            username = str(form.get("username", ""))
            password = str(form.get("password", ""))
            return username, password
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid form data payload.",
            )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description=(
        "Authenticates with username/email and password, issuing a signed JWT access token. "
        "Supports both application/x-www-form-urlencoded (OAuth2 / Swagger UI) and application/json."
    ),
    openapi_extra={
        "requestBody": {
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "Username or email"},
                            "password": {"type": "string", "description": "Password"},
                            "grant_type": {"type": "string", "default": "password"},
                            "scope": {"type": "string", "default": ""},
                            "client_id": {"type": "string"},
                            "client_secret": {"type": "string"},
                        },
                        "required": ["username", "password"],
                    }
                },
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "Username or email"},
                            "password": {"type": "string", "description": "Password"},
                        },
                        "required": ["username", "password"],
                    }
                },
            }
        }
    },
)
async def login(
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    raw_username, raw_password = await get_login_credentials(request)

    if not raw_username or not raw_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both username and password are required.",
        )

    identifier = raw_username.strip().lower()

    # Generic error detail to prevent account enumeration
    invalid_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Find user by username or email
    user = (
        db.query(User)
        .filter(
            (User.username == identifier) | (User.email == identifier)
        )
        .first()
    )

    if not user:
        # Constant-time protection
        raise invalid_credentials_exception

    if not verify_password(raw_password, user.hashed_password):
        raise invalid_credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create signed JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        subject=user.id,
        role=user.role,
        expires_delta=access_token_expires,
        extra_claims={
            "username": user.username,
            "email": user.email,
        },
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current User Profile",
    description="Returns the profile and role of the currently authenticated user.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)
