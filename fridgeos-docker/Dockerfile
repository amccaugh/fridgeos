FROM python:3.12-alpine

WORKDIR /app

COPY ../fridgeos /app/fridgeos-src/
RUN pip install -e fridgeos-src/

COPY config /app/config/
COPY scripts /app/scripts/

CMD ["python", "--version"]