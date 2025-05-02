FROM python:3.12-alpine

WORKDIR /app

RUN pip install fridgeos

COPY hal-server.py /app/hal-server.py
COPY monitor-server.py /app/monitor-server.py