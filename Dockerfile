FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home mrx
USER mrx
ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["mrx-mcp-http"]
