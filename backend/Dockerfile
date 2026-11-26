FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Keep the database writable without running the web process as root.
RUN useradd --system --uid 10001 --create-home notifier \
    && mkdir /data && chown notifier:notifier /data
COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY migrations ./migrations
RUN pip install --no-cache-dir .
USER notifier
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
