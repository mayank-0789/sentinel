# Sentinel — the policy-gated SRE copilot service
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY sentinel ./sentinel
COPY policies ./policies
RUN pip install --no-cache-dir .
EXPOSE 9099
CMD ["uvicorn", "sentinel.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "9099"]
