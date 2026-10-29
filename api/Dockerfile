FROM python:3.11.17-slim-trixie

WORKDIR /transit-tracker/api/

COPY requirements.txt /transit-tracker/api/

RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --no-create-home appuser

USER appuser

COPY --chown=appuser:appuser app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
