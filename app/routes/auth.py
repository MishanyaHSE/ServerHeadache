import logging
from datetime import timedelta, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserQuestions, UserVerification, RefreshToken
from app.schemas import UserCreate, UserResponse, PasswordReset, Token, UserAuth
from app.utils.encryption import validate_verification_code, get_password_hash, verify_password, create_access_token, \
    oauth2_scheme, get_current_user
from app.utils.verification import generate_verification_code, send_verification_code, is_valid_refresh_token

router = APIRouter(prefix="", tags=["Auth"])
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_MINUTES = 30 * 6000
logger = logging.getLogger(__name__)




@router.post("/register", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        existing_user = (await db.execute(select(User).where(User.email == user.email))).scalar_one_or_none()
        if existing_user and existing_user.is_verified:
            raise HTTPException(status_code=400, detail="Email already registered")
        elif existing_user and not existing_user.is_verified:
            await db.delete(
                (await db.execute(select(UserQuestions).where(UserQuestions.user_id == existing_user.id)))
                .scalar_one_or_none())
            await db.commit()
            await db.delete((await db.execute(select(UserVerification).where(UserVerification.email == existing_user.email)))
                            .scalar_one_or_none())
            await db.commit()
            await db.delete(existing_user)
            await db.commit()

        new_user = User(
            name=user.name,
            email=str(user.email),
            password=get_password_hash(user.password),  # Хешируем пароль
            is_verified=False
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        user_verification = generate_verification_code(new_user.email)
        db.add(user_verification)
        await db.commit()
        await db.refresh(user_verification)
        send_verification_code(new_user.email, user_verification.code)
        new_user_questions = UserQuestions(user_id=new_user.id, time_question=True, duration_question=True,
                                           intensity_question=True, pain_type_question=True, area_question=True,
                                           triggers_question=True, medicine_question=True, symptoms_question=True,
                                           pressure_question=True, comment_question=True)
        db.add(new_user_questions)
        await db.commit()
        await db.refresh(new_user_questions)
        return new_user
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating user")


@router.patch("/users/reset-password")
async def reset_password(reset_data: PasswordReset, db: AsyncSession = Depends(get_db)):
    if validate_verification_code(reset_data.code, reset_data.email, db):
        user = (await db.execute(select(User).where(User.email == reset_data.email))).scalar_one_or_none()
        user.password = get_password_hash(reset_data.password)
        await db.commit()
        await db.refresh(user)
    else:
        raise HTTPException(status_code=404, detail="Code not found or has expired")


@router.post("/register/{email}/{code}/")
async def verify_code(email: str, code: str, db: AsyncSession = Depends(get_db)):
    is_valid = await validate_verification_code(code, email, db)
    if is_valid:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        user.is_verified = True
        await db.commit()
        await db.refresh(user)
        return {'message': 'Verification code is valid'}
    else:
        raise HTTPException(status_code=400, detail="Code is invalid or has been expired")


@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: UserAuth, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == form_data.username))).scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password) or not user.is_verified:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_delta = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    access_token, refresh_token = await create_access_token(user.id, data={"sub": user.email},
                                                            expires_delta=access_token_expires,
                                                            refresh_delta=refresh_token_delta)
    db_token = RefreshToken(
        token=refresh_token,
        user_id=user.id,
        expires_at=datetime.utcnow() + refresh_token_delta,
        revoked=False
    )
    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}



@router.post("/login/refresh", response_model=Token)
async def refresh_token(refreshtoken: str = Depends(oauth2_scheme), user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_delta = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    if is_valid_refresh_token(refreshtoken):
        new_token, refresh_token = await create_access_token(user.id, data={"sub": user.email},
                                                             expires_delta=access_token_expires,
                                                             refresh_delta=refresh_token_delta)
        db_token = RefreshToken(
            token=refresh_token,
            user_id=user.id,
            expires_at=datetime.utcnow() + access_token_expires,
            revoked=False
        )
        db.add(db_token)
        await db.commit()
        await db.refresh(db_token)
        return {"access_token": new_token, "refresh_token": refresh_token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


@router.post("/users/forgot-password/{email}")
async def forgot_password(email: str, db: AsyncSession = Depends(get_db)):
    try:
        logger.info(email)
        existing_user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        logger.info('HERE')
        if existing_user and existing_user.is_verified:
            existing_code = (await db.execute(
                select(UserVerification).where(UserVerification.email == email))).scalar_one_or_none()
            logger.info('HERE2')

            await db.delete(existing_code)
            await db.commit()
            user_verification = generate_verification_code(email)
            db.add(user_verification)
            await db.commit()
            await db.refresh(user_verification)
            send_verification_code(email, user_verification.code)
            return

        elif existing_user and not existing_user.is_verified or not existing_user:
            logger.info('HERE3')
            raise HTTPException(status_code=400, detail="Email not registered")
    except:
        raise HTTPException(status_code=400, detail="Email not registered")
