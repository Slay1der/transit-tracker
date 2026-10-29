FROM python:3.11.17-slim-trixie

WORKDIR /transit-tracker/api/


COPY requirements.txt  /transit-tracker/api/

RUN pip install -r requiremets.txt && useradd appuser

USER appuser

COPY app ./app

CMD  ["uvicorn", "app.main:app", "--host 0.0.0.0" , "--port", "8000"]





