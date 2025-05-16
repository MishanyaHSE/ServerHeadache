import logging
import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserVerification
from app.schemas import TokenData

pwd_context = CryptContext(schemes=["bcrypt"], default="bcrypt")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)

async def create_access_token(user_id: int, data: dict, expires_delta: timedelta | None = None,
                              refresh_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    refresh = datetime.utcnow() + refresh_delta
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    to_encode.update({'exp': refresh})
    refresh_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, refresh_jwt

async def validate_verification_code(code, email, db):
    existing_user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing_user is None:
        logger.info(f"User not found")
        return False
    user_verification = (
        await db.execute(select(UserVerification).where(UserVerification.email == email))).scalar_one_or_none()
    if user_verification is None:
        logger.info(f"Verification code not found")
        return False
    if user_verification.code != code:
        logger.info(f"Email verification code mismatch")
        if user_verification.attempts == 2:
            await db.delete(user_verification)
            await db.delete(existing_user)
        user_verification.attempts += 1
        return False
    else:
        if user_verification.created_at > datetime.now() + timedelta(minutes=15):
            logger.info(f"Email verification code expired")
            await db.delete(user_verification)
            return False
        else:
            return True


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = (await db.execute(select(User).where(User.email == token_data.email))).scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user