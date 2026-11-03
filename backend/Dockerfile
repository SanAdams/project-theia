FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# main.py mounts StaticFiles(directory="static"), which raises at startup if
# the directory is missing. The scan router creates crops/ and debug/ under it,
# so the runtime user must own it.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p static \
    && chown -R appuser:appuser static

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
