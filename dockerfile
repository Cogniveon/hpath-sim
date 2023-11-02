FROM python:3.11-slim

RUN apt update && apt upgrade -y
COPY hpath-sim/requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

COPY /hpath-sim /app/hpath-sim

WORKDIR /app/hpath-sim
CMD python -m restful.server
