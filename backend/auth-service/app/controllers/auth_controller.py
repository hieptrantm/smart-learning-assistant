from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from datetime import datetime, timedelta
import requests as http_requests
import jwt

from app.schemas.auth import *
from app.models import User, AuthProvider
from app.services import *

from app.database import get_db
from app.config import GOOGLE_CLIENT_ID, SECRET_KEY

if not GOOGLE_CLIENT_ID:
    print("GOOGLE_CLIENT_ID not loaded, check config import or config file")

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.get("/")
def root():
    return {"service": "auth-service", "status": "running"}

@auth_router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    if request.provider == "email":
        # Find user with email provider
        auth_provider = db.query(AuthProvider).filter(
            AuthProvider.provider == "email",
            AuthProvider.provider_id == request.email
        ).first()
        
        if not auth_provider:
            raise HTTPException(status_code=401, detail="User not found")
        
        user = db.query(User).filter(User.id == auth_provider.user_id).first()
        if not user or not user.password_hash:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")

    elif request.provider == "google":
        if not request.provider_id:
            raise HTTPException(status_code=400, detail="Missing provider_id for Google login")
        
        auth_provider = db.query(AuthProvider).filter(
            AuthProvider.provider == "google",
            AuthProvider.provider_id == request.provider_id
        ).first()
        
        if not auth_provider:
            # Create new user and auth provider
            user = User(
                username=request.email.split("@")[0],
                email=request.email,
            )
            db.add(user)
            db.flush()  # Get user.id before creating auth_provider
            
            auth_provider = AuthProvider(
                user_id=user.id,
                provider="google",
                provider_id=request.provider_id
            )
            db.add(auth_provider)
            db.commit()
            db.refresh(user)
        else:
            user = db.query(User).filter(User.id == auth_provider.user_id).first()
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    user.last_login = datetime.utcnow()
    db.commit()

    access_token, access_expire = create_access_token({"sub": user.email})
    print(f"ACCESS TOKEN INFO: {access_token}, expires at {access_expire}")
    refresh_token = create_refresh_token({"sub": user.email})
    print(f"REFRESH TOKEN INFO: {refresh_token}")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": int(access_expire.timestamp() * 1000),
        "token_type": "bearer"
    }

@auth_router.get("/verify")
def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return {"valid": True, "email": payload.get("sub")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@auth_router.patch("/verify-email")
def verify_email(request: VerifyEmailRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(request.token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "email_verification":
            raise HTTPException(status_code=400, detail="Invalid token type")
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Verification link has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.email_verified:
        return {
            "message": "Email already verified",
            "user": {"username": user.username, "email": user.email, "email_verified": True}
        }
    
    user.email_verified = True
    db.commit()
    db.refresh(user)
    
    return {
        "message": "Email verified successfully",
        "user": {"username": user.username, "email": user.email, "email_verified": user.email_verified}
    }

@auth_router.post("/send-verification")
def send_verification(request: SendVerificationRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    
    token = generate_verification_token_email(user.email)
    email_sent = send_verification_email(user.email, user.username, token)
    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send verification email")
    return {"message": "Verification email sent successfully"}

@auth_router.post("/register", response_model=TokenResponse)
def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password)
    )
    db.add(user)
    db.flush()  # Get user.id
    
    # Create email auth provider
    auth_provider = AuthProvider(
        user_id=user.id,
        provider="email",
        provider_id=request.email
    )
    db.add(auth_provider)
    db.commit()
    db.refresh(user)

    access_token, access_expire = create_access_token({"sub": user.email})
    refresh_token = create_refresh_token({"sub": user.email})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": int(access_expire.timestamp() * 1000),
        "token_type": "bearer"
    }

@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms="HS256")
        email = payload.get("sub")
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token type")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_access_token, access_expire = create_access_token({"sub": user.email})
    return {
        "access_token": new_access_token,
        "refresh_token": request.refresh_token,
        "expires_at": int(access_expire.timestamp() * 1000),
        "token_type": "bearer"
    }

@auth_router.get("/me", response_model=UserResponse)
async def get_me(user=Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all auth providers for this user
    auth_providers = db.query(AuthProvider).filter(AuthProvider.user_id == db_user.id).all()
    providers = [ap.provider for ap in auth_providers]
    
    return {
        "id": str(db_user.id),
        "username": db_user.username,
        "email": db_user.email,
        "avatar_url": db_user.avatar_url,
        "email_verified": db_user.email_verified,
        "provider": providers[0] if providers else None,  # Primary provider
        "providers": providers,  # All linked providers
        "has_password": db_user.password_hash is not None
    }

@auth_router.post("/logout")
async def logout():
    return {"message": "Logged out successfully"}

@auth_router.post("/google/login", response_model=TokenResponse)
async def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        idinfo = id_token.verify_oauth2_token(request.id_token, google_requests.Request(), GOOGLE_CLIENT_ID, clock_skew_in_seconds=10)
        if idinfo['aud'] != GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=401, detail="Invalid token audience")
        
        google_user_id = idinfo['sub']
        email = idinfo.get('email')
        email_verified = idinfo.get('email_verified', False)
        name = idinfo.get('name', '')
        picture = idinfo.get('picture')
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        # Check if Google provider exists
        auth_provider = db.query(AuthProvider).filter(
            AuthProvider.provider == "google",
            AuthProvider.provider_id == google_user_id
        ).first()
        
        if auth_provider:
            # Existing user with Google login
            user = db.query(User).filter(User.id == auth_provider.user_id).first()
            if not user.email_verified and email_verified:
                user.email_verified = True
            if picture:
                user.avatar_url = picture
            user.last_login = datetime.utcnow()
        else:
            # Check if user exists with this email (account linking)
            user = db.query(User).filter(User.email == email).first()
            if user:
                # Link Google account to existing user
                auth_provider = AuthProvider(
                    user_id=user.id,
                    provider="google",
                    provider_id=google_user_id
                )
                db.add(auth_provider)
                if not user.email_verified and email_verified:
                    user.email_verified = True
                if picture:
                    user.avatar_url = picture
                user.last_login = datetime.utcnow()
            else:
                # Create new user
                user = User(
                    email=email,
                    username=name or email.split("@")[0],
                    avatar_url=picture,
                    email_verified=email_verified,
                    last_login=datetime.utcnow()
                )
                db.add(user)
                db.flush()  # Get user.id
                
                auth_provider = AuthProvider(
                    user_id=user.id,
                    provider="google",
                    provider_id=google_user_id
                )
                db.add(auth_provider)
        
        db.commit()
        db.refresh(user)
        
        access_token, access_expire = create_access_token({"sub": user.email})
        print(f"ACCESS TOKEN INFO: {access_token}, expires at {access_expire}")
        refresh_token = create_refresh_token({"sub": user.email})
        print(f"REFRESH TOKEN INFO: {refresh_token}")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_at": int(access_expire.timestamp() * 1000),
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@auth_router.post("/google/login-access-token", response_model=TokenResponse)
def google_login_access_token(request: GoogleAccessTokenRequest, db: Session = Depends(get_db)):
    """
    Authenticate using a Google OAuth2 access_token (implicit flow).
    Verifies the token via Google's userinfo endpoint, then creates/returns the user JWT.
    Used when the frontend requests both calendar + auth scopes in a single OAuth flow.
    """
    try:
        # Verify the access_token by fetching user info from Google
        resp = http_requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {request.access_token}"},
            timeout=10,
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google access token")

        userinfo = resp.json()
        google_user_id = userinfo.get("sub")
        email = userinfo.get("email")
        email_verified = userinfo.get("email_verified", False)
        name = userinfo.get("name", "")
        picture = userinfo.get("picture")

        if not email or not google_user_id:
            raise HTTPException(status_code=400, detail="Email not provided by Google")

        # Reuse same user lookup / creation logic as /google/login
        auth_provider = db.query(AuthProvider).filter(
            AuthProvider.provider == "google",
            AuthProvider.provider_id == google_user_id
        ).first()

        if auth_provider:
            user = db.query(User).filter(User.id == auth_provider.user_id).first()
            if not user.email_verified and email_verified:
                user.email_verified = True
            if picture:
                user.avatar_url = picture
            user.last_login = datetime.utcnow()
        else:
            user = db.query(User).filter(User.email == email).first()
            if user:
                auth_provider = AuthProvider(
                    user_id=user.id,
                    provider="google",
                    provider_id=google_user_id,
                )
                db.add(auth_provider)
                if not user.email_verified and email_verified:
                    user.email_verified = True
                if picture:
                    user.avatar_url = picture
                user.last_login = datetime.utcnow()
            else:
                user = User(
                    email=email,
                    username=name or email.split("@")[0],
                    avatar_url=picture,
                    email_verified=email_verified,
                    last_login=datetime.utcnow(),
                )
                db.add(user)
                db.flush()
                auth_provider = AuthProvider(
                    user_id=user.id,
                    provider="google",
                    provider_id=google_user_id,
                )
                db.add(auth_provider)

        db.commit()
        db.refresh(user)

        access_token, access_expire = create_access_token({"sub": user.email})
        refresh_token = create_refresh_token({"sub": user.email})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_at": int(access_expire.timestamp() * 1000),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@auth_router.post("/request-set-password-email")
async def request_set_password_email(current_user: User = Depends(get_current_user)):
    if current_user.password_hash:
        raise HTTPException(status_code=400, detail="User already has a password. Use change-password endpoint instead.")
    
    token = generate_verification_token_email(current_user.email)
    email_sent = send_set_password_email(current_user.email, current_user.username, token)
    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send set password email")
    return {"message": "Set password email sent successfully"}

@auth_router.post("/request-change-password-email")
async def request_change_password_email(current_user: User = Depends(get_current_user)):
    token = generate_reset_password_token(current_user.email)
    email_sent = send_change_password_email(current_user.email, current_user.username, token)
    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send change password email")
    return {"message": "Change password email sent successfully"}

@auth_router.patch("/set-password")
async def set_password(request: SetPasswordRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(request.token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") not in ["reset_password", "email_verification"]:
            raise HTTPException(status_code=400, detail="Invalid token type")
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.password_hash:
        raise HTTPException(status_code=400, detail="User already has a password. Use change-password endpoint instead.")
    
    user.password_hash = hash_password(request.password)
    
    # Add email auth provider if it doesn't exist lmao
    email_provider = db.query(AuthProvider).filter(
        AuthProvider.user_id == user.id,
        AuthProvider.provider == "email"
    ).first()
    
    if not email_provider:
        auth_provider = AuthProvider(
            user_id=user.id,
            provider="email",
            provider_id=user.email
        )
        db.add(auth_provider)
    
    db.commit()
    return {"message": "Password set successfully. You can now login with email and password.", "has_password": True}

@auth_router.patch("/change-password")
async def change_password(request: SetPasswordRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(request.token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") not in ["reset_password"]:
            raise HTTPException(status_code=400, detail="Invalid token type")
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.password_hash = hash_password(request.password)
    db.commit()
    return {"message": "Password changed successfully. You can now login again"}

@auth_router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if user and user.password_hash:
        token = generate_reset_password_token(user.email)
        send_reset_password_email(user.email, user.username, token)
    return {"message": "If an account exists with this email, a password reset link has been sent."}

@auth_router.post("/test-email")
def test_email(request: TestEmailRequest):
    email_sent = send_test_email(request.email, request.username, "test-token")
    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send test email")
    return {"message": "Test email sent successfully"}