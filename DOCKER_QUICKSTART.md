# Docker Quick Start Guide

This guide helps you get the GA4/GSC Web Interface running with Docker quickly.

## Prerequisites

1. **Install Docker** and **Docker Compose**
2. **Set up Google OAuth2 credentials** (see main README.md)

## Setup Steps

### 1. Prepare Authentication Directory

```bash
# Create directories
mkdir -p auth data

# Copy your Google OAuth2 credentials
cp your-client-secrets.json auth/client_secrets.json
```

### 2. Run with Docker Compose

```bash
# Build and start (first time)
docker compose up --build

# Start without rebuilding
docker compose up

# Run in background
docker compose up -d
```

### 3. Access the Application

Open your browser and go to: **http://localhost:7860**

## Configuration

### Environment Variables

Edit `docker-compose.yaml` to customize:

```yaml
environment:
  - GRADIO_SERVER_NAME=0.0.0.0        # Server host
  - GRADIO_SERVER_PORT=7860            # Server port
  - GRADIO_AUTH=admin:password123      # Optional: Add authentication
  - GRADIO_SHARE=true                  # Optional: Create public link
```

### Change Port

To run on port 8080 instead of 7860:

```yaml
ports:
  - "8080:7860"
```

## Common Commands

```bash
# View logs
docker compose logs -f ga4-gsc-web

# Stop the application
docker compose down

# Rebuild after code changes
docker compose down
docker compose up --build

# Remove containers and volumes
docker compose down -v
```

## Troubleshooting

### Authentication Issues

1. Ensure `client_secrets.json` is in the `auth/` directory
2. Check file permissions: `ls -la auth/`
3. Verify the file format is correct (valid JSON)

### Port Conflicts

If port 7860 is already in use:

```bash
# Option 1: Change port in docker-compose.yaml
ports:
  - "8080:7860"

# Option 2: Create override file
echo 'services:
  ga4-gsc-web:
    ports:
      - "8080:7860"' > docker-compose.override.yaml
```

### Container Won't Start

Check the logs:

```bash
docker compose logs ga4-gsc-web
```

Common issues:
- Missing authentication files
- Port already in use
- Insufficient permissions on mounted volumes

## Manual Docker Commands

If you prefer not to use Docker Compose:

```bash
# Build image
docker build -t ga4-gsc-web .

# Run container
docker run -d \
  --name ga4-gsc-web \
  -p 7860:7860 \
  -v $(pwd)/auth:/app/auth \
  -v $(pwd)/data:/app/data \
  -e GRADIO_AUTH=admin:password123 \
  ga4-gsc-web

# View logs
docker logs -f ga4-gsc-web

# Stop container
docker stop ga4-gsc-web
docker rm ga4-gsc-web
```

## File Structure

After setup, your directory should look like:

```
.
├── auth/
│   └── client_secrets.json         # Your OAuth2 credentials
├── data/                           # Generated data and tokens
├── docker-compose.yaml            # Docker Compose configuration
├── Dockerfile                     # Docker image definition
├── ga4_gsc_web_interface.py       # Main application
└── ... (other project files)
```

## Production Deployment

For production, consider:

1. **Use a reverse proxy** (nginx/traefik)
2. **Enable HTTPS** with SSL certificates
3. **Set up authentication** (`GRADIO_AUTH`)
4. **Use external volumes** for persistent data
5. **Configure logging** and monitoring

Example nginx configuration is commented out in `docker-compose.yaml`.