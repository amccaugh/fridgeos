FROM python:3.12-alpine

WORKDIR /app

COPY fridgeos /app/fridgeos-src/
RUN pip install -e fridgeos-src/

COPY fridgeos-docker/config /app/config/
COPY fridgeos-docker/scripts /app/scripts/

CMD ["python", "--version"]