FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app


# 2. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt



# 4. Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"]