FROM python:3.11.17-slim-trixie

WORKDIR /transit-tracker/worker/

COPY requirements.txt /transit-tracker/worker/

RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --no-create-home appuser

USER appuser

COPY --chown=appuser:appuser worker.py route.py ./

EXPOSE 9100

CMD ["python", "worker.py"]
