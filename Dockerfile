FROM python:3.12
WORKDIR /app
COPY app/requirements.txt .
RUN pip install -r requirements.txt
RUN pip install fastapi
RUN pip install uvicorn

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
