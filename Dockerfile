FROM python:3.9-slim

# Install Redis
RUN apt-get update && apt-get install -y redis-server

# Set up app directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p logs article_exports analysis_outputs src

# Copy source files
COPY src/ src/
COPY start.sh .
RUN chmod +x start.sh

# Expose ports
EXPOSE 8000 6381

# Start services
CMD ["./start.sh"] 