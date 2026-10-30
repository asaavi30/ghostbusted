# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ghostbusted ./ghostbusted
EXPOSE 8000
# Web app. Hosts like Render set $PORT; locally it defaults to 8000.
# For the daily job, override the command with:  python -m ghostbusted.daily
CMD ["sh", "-c", "uvicorn ghostbusted.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
