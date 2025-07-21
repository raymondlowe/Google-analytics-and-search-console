# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt pyproject.toml ./

# Create a modified requirements.txt without win-unicode-console for Linux containers
RUN grep -v "win-unicode-console" requirements.txt > requirements-linux.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-linux.txt

# Copy application code
COPY *.py ./
COPY *.md ./
COPY docker-entrypoint.sh ./

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Create directories for authentication files and data
RUN mkdir -p /app/auth /app/data

# Expose the port that Gradio runs on
EXPOSE 7860

# Set entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]