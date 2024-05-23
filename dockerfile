FROM python:3.11-slim

RUN apt update && apt upgrade -y

COPY hpath-sim/requirements.in /requirements.in

RUN pip install pip-tools && \
    pip-compile requirements.in && \
    pip-sync
 
COPY /hpath-sim /app/hpath-sim
 
WORKDIR /app/hpath-sim
CMD python -m restful.server