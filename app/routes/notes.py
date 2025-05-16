from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Note
from app.schemas import NoteCreate, NoteResponse
from app.utils.encryption import get_current_user

router = APIRouter(prefix="", tags=["Notes"])


@router.get("/users/notes/one/{date}/", response_model=NoteCreate)
async def get_one_note(date: datetime, current_user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    query = (
        select(Note)
        .where(
            and_(
                Note.user_id == current_user.id,
                extract('month', Note.date) == date.month,
                extract('year', Note.date) == date.year,
                extract('day', Note.date) == date.day
            )
        )
    )
    result = await db.execute(query)
    if result.scalars().first():
        return result.scalars().one_or_none()
    else:
        raise HTTPException(status_code=404, detail="Note not found")


@router.post("/users/notes", response_model=NoteResponse)
async def write_users_notes(note: NoteCreate, current_user: User = Depends(get_current_user),
                            db: AsyncSession = Depends(get_db)):

    db_note = Note(user_id=current_user.id, **note.model_dump())
    db.add(db_note)
    await db.commit()
    await db.refresh(db_note)
    return db_note


@router.delete("/users/notes/one/{date}/")
async def delete_note_by_date(date: datetime, current_user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    note = await db.execute(
        select(Note)
        .where(
            and_(
                Note.user_id == current_user.id,
                extract('day', Note.date) == date.day,
                extract('month', Note.date) == date.month,
                extract('year', Note.date) == date.year
            )
        )
    )
    note = note.scalar_one_or_none()

    if not note:
        raise HTTPException(
            status_code=404,
            detail="Note not found for this date"
        )
    await db.delete(note)
    await db.commit()

    return {"message": "Note successfully deleted"}


@router.get("/users/notes/{date}/", response_model=list[NoteResponse])
async def read_users_notes(date: datetime, current_user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    query = (
        select(Note)
        .where(
            and_(
                Note.user_id == current_user.id,
                extract('month', Note.date) == date.month,
                extract('year', Note.date) == date.year
            )
        )
        .order_by(Note.date)
    )
    result = await db.execute(query)
    return result.scalars().all()