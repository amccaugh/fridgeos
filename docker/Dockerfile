FROM python:3.12-alpine

WORKDIR /app

# Install fridgeos in editable mode during build (repo root has pyproject.toml + fridgeos/ package)
COPY pyproject.toml uv.lock /app/fridgeos-src/
COPY fridgeos /app/fridgeos-src/fridgeos/
RUN pip install -e /app/fridgeos-src/

CMD ["python", "--version"]