from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserCreate, UserLogin, Token, UserResponse
from security import (
    hash_password,
    verify_password,
    create_access_token,
    get_token_from_header,
    blacklist_token,
)
import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=Token)
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    existing_username = db.query(User).filter(User.username == user.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    # Create user
    user_id = str(uuid.uuid4())
    db_user = User(
        id=user_id,
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        is_guest=False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Generate token
    access_token = create_access_token(user_id=db_user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "is_guest": db_user.is_guest,
            "created_at": db_user.created_at,
        },
    }


@router.post("/login", response_model=Token)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    # Find user by email or username
    db_user = (
        db.query(User)
        .filter((User.email == user.email) | (User.username == user.email))
        .first()
    )
    if not db_user or not db_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Verify password
    if not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Generate token
    access_token = create_access_token(user_id=db_user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "is_guest": db_user.is_guest,
            "created_at": db_user.created_at,
        },
    }


@router.post("/guest", response_model=UserResponse)
async def create_guest(db: Session = Depends(get_db)):
    user_id = str(uuid.uuid4())
    username = f"Guest_{uuid.uuid4().hex[:8].upper()}"

    db_user = User(id=user_id, username=username, is_guest=True)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {
        "id": db_user.id,
        "username": db_user.username,
        "is_guest": db_user.is_guest,
        "created_at": db_user.created_at,
    }


@router.post("/logout")
async def logout(request: Request):
    """Logout and invalidate the current token."""
    try:
        token = get_token_from_header(request)
        blacklist_token(token)
        return {"message": "Successfully logged out"}
    except HTTPException:
        return {"message": "No active session"}
