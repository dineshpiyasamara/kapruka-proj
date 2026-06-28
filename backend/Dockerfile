FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies and runtime requirements.
COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt fastapi uvicorn python-dotenv

# Copy only the backend application files.
COPY backend ./backend
WORKDIR /app/backend

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
