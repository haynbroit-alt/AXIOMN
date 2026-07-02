# AXIOMN Gateway — one-command deployment:
#   docker build -t axiomn .
#   docker run -p 8000:8000 \
#     -e AXIOMN_API_KEYS=your-secret \
#     -e ANTHROPIC_API_KEY=sk-... \
#     axiomn
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt pyproject.toml ./
COPY axiomn ./axiomn
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e .

RUN useradd --create-home axiomn && chown -R axiomn /app
USER axiomn

EXPOSE 8000
CMD ["uvicorn", "axiomn.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
