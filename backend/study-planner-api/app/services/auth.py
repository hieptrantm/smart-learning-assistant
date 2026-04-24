"""
auth.py – JWT token verification (shared secret with auth-service).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, ALGORITHM
from app.database import get_db

security = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> int:
    """Decode JWT and return user_id.

    Accepts both token styles:
    - user_id in `user_id` or `sub` claim
    - email in `sub` claim (legacy auth-service format)
    """
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_claim = payload.get("user_id")
        sub_claim = payload.get("sub")

        if user_claim is not None:
            return int(user_claim)

        if sub_claim is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        try:
            return int(sub_claim)
        except (TypeError, ValueError):
            row = db.execute(
                text("SELECT id FROM users WHERE email = :email LIMIT 1"),
                {"email": str(sub_claim)},
            ).fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            return int(row[0])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
