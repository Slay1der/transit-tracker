FROM python:3.11.17-slim-trixie

WORKDIR /transit-tracker/worker/


COPY requirements.txt  /transit-tracker/worker/

RUN pip install -r requirements.txt && useradd appuser

USER appuser

COPY worker.py route.py ./

CMD  ["pyhton","worker.py"]





