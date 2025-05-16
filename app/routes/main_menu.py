from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.database import get_db
from app.models import User, Note, UserQuestions
from app.schemas import ReportCreate, StatisticsCreate, QuestionsResponse, QuestionsData, UserResponse
from app.utils.encryption import get_current_user
from app.utils.reports import send_report_to_email, create_csv, create_pdf
from app.utils.statistics import create_statistics

router = APIRouter(prefix="", tags=["Main"])


@router.post("/users/report")
async def generate_report(report: ReportCreate, current_user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    query = (
        select(Note)
        .where(
            and_(
                Note.user_id == current_user.id,
                Note.date >= report.date_start,
                Note.date <= report.date_end
            )
        )
        .order_by(Note.date)
    )
    result = (await db.execute(query)).scalars().all()
    if report.format == 0:
        buffer = create_pdf(result)
        if report.send_to_mail:
            return StreamingResponse(buffer, media_type="application/pdf",
                                     headers={f"Content-Disposition": f'attachment; filename="report.pdf"'})
        else:
            send_report_to_email(current_user.email, buffer, 'pdf')
    else:
        buffer = create_csv(result)
        if report.send_to_mail:
            return StreamingResponse(buffer, media_type="text/csv",
                                     headers={f"Content-Disposition": f'attachment; filename="report.csv"'})
        else:
            send_report_to_email(current_user.email, buffer, 'csv')


@router.post("/users/statistics")
async def get_statistics(statistics_info: StatisticsCreate, current_user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    return await create_statistics(statistics_info.date_start, statistics_info.date_end, current_user.id, db)


@router.put("/users/questions", response_model=QuestionsResponse)
async def update_questions(questions_data: QuestionsData, current_user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    questions = (
        await db.execute(select(UserQuestions).where(UserQuestions.user_id == current_user.id))).scalar_one_or_none()
    questions.time_question = questions_data.time_question
    questions.duration_question = questions_data.duration_question
    questions.intensity_question = questions_data.intensity_question
    questions.pain_type_question = questions_data.pain_type_question
    questions.area_question = questions_data.area_question
    questions.triggers_question = questions_data.triggers_question
    questions.medicine_question = questions_data.medicine_question
    questions.symptoms_question = questions_data.symptoms_question
    questions.pressure_question = questions_data.pressure_question
    questions.comment_question = questions_data.comment_question
    await db.commit()
    await db.refresh(questions)
    return questions


@router.get("/users/questions", response_model=QuestionsResponse)
async def read_users_questions(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    questions = (
        await db.execute(select(UserQuestions).where(UserQuestions.user_id == current_user.id))).scalar_one_or_none()
    return questions


@router.get("/users/{user_id}/", response_model=UserResponse)
async def read_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
