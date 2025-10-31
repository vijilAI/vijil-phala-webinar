# Builder stage
FROM python:3.11 AS builder

WORKDIR /app

# Copy requirements and install with caching
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --user --no-warn-script-location -r requirements.txt

# Runtime stage
FROM python:3.11-slim AS runtime

# Create user with home directory
RUN adduser --disabled-password --home /home/appuser appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app /home/appuser

# Set environment variables
ENV HOME=/home/appuser \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH

# Install system dependencies
RUN apt-get update && \
    apt-get install -y gosu curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy documentation files
COPY --chown=appuser:appuser data/docs /app/data/docs

# Copy application code
COPY --chown=appuser:appuser agent.py tools.py ./

# Expose port
EXPOSE 8000

# Switch to non-root user
USER appuser

# Run the application
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8000"]
