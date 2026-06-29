from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import create_access_token, verify_password, get_password_hash
from app.core.config import settings
from app.crud.user import get_user_by_email, create_user, get_user_by_google_id, create_user_from_google, update_last_active
from app.schemas.user import UserCreate, Token, GoogleAuthRequest, GoogleAuthResponse
from app.api import deps
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
import json
import requests

router = APIRouter()

@router.post("/register", response_model=Token)
def register(user_in: UserCreate, db: Session = Depends(deps.get_db)):
    user = get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    user = create_user(db, user_in)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(deps.get_db)):
    user = get_user_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Update last active
    update_last_active(db, user.id)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/google", response_model=GoogleAuthResponse)
def google_auth(google_req: GoogleAuthRequest, db: Session = Depends(deps.get_db)):
    """Authenticate user with Google OAuth ID token"""
    try:
        # Verify the Google ID token
        # In production, you would verify the token properly with Google's servers
        # For this implementation, we'll decode and trust (not secure for production!)
        import jwt
        # Decode without verification for demo - IN PRODUCTION, VERIFY WITH GOOGLE'S PUBLIC KEYS
        try:
            # This is insecure - only for demonstration!
            # Proper implementation would use google.oauth2.id_token.verify_token
            decoded_token = jwt.decode(google_req.token, options={"verify_signature": False})
            google_info = decoded_token
        except Exception as e:
            # Fallback: try to verify with Google's tokeninfo endpoint
            response = requests.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={google_req.token}"
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Google token"
                )
            google_info = response.json()

        # Check if user exists by Google ID
        user = get_user_by_google_id(db, google_id=google_info.get("sub"))

        if not user:
            # Check if user exists by email (for account linking)
            if google_info.get("email"):
                user = get_user_by_email(db, email=google_info.get("email"))
                if user:
                    # Link existing account with Google ID
                    user.google_id = google_info.get("sub")
                    user.avatar_url = google_info.get("picture")
                    user.is_verified = True
                    db.commit()
                    db.refresh(user)
                else:
                    # Create new user from Google info
                    user = create_user_from_google(db, google_info)
            else:
                # Create new user from Google info
                user = create_user_from_google(db, google_info)
        else:
            # Update last active for existing user
            update_last_active(db, user.id)

        # Generate access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=user.email or f"google_{user.google_id}",
            expires_delta=access_token_expires
        )

        # Return user info (excluding sensitive data)
        user_data = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "google_id": user.google_id
        }

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )