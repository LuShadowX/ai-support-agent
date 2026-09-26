FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml ./
COPY app ./app
RUN pip install .
COPY data ./data
COPY static ./static
EXPOSE 8000
# Index documents on start (fast when nothing changed), then serve.
CMD ["sh", "-c", "python -m app.ingest && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
