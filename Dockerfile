FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EMBER_DATA_DIR=/app/runtime
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
 && useradd --uid 10001 --create-home ember \
 && mkdir -p /app/runtime && chown ember:ember /app/runtime
COPY --chown=ember:ember ember ./ember
COPY --chown=ember:ember scripts/healthcheck.py ./scripts/healthcheck.py
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "scripts/healthcheck.py"]
CMD ["python", "-m", "ember", "serve", "--host", "0.0.0.0", "--port", "8000"]
