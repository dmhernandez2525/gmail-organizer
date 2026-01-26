# Gmail Organizer - Streamlit App
# Build: docker build -t gmail-organizer .
# Run:   docker-compose up -d

FROM python:3.11-slim

LABEL maintainer="Daniel Hernandez"
LABEL description="Gmail Organizer with AI-powered classification"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY gmail_organizer/ ./gmail_organizer/
COPY app.py .

# Create directories for data persistence
RUN mkdir -p /app/credentials /app/logs /app/.email-cache

# Create non-root user
RUN useradd -m gmailorg && chown -R gmailorg:gmailorg /app
USER gmailorg

# Expose Streamlit port
EXPOSE 8501

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Start Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
