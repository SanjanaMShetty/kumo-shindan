FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install ".[openai]"

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    DB_PATH=/data/kubesleuth.db
COPY --from=build /install /usr/local
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /data \
    && chown 10001:10001 /data
USER 10001
EXPOSE 8000
CMD ["uvicorn", "kubesleuth.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
