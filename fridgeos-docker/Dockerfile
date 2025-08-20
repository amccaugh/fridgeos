FROM python:3.12-alpine

WORKDIR /app

# Install fridgeos in editable mode during build
COPY fridgeos /app/fridgeos-src/
RUN pip install -e /app/fridgeos-src/

CMD ["python", "--version"]