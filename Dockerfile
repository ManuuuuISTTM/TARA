# Use a small Python image
FROM python:3.11-slim

# Install system packages we need for audio/voice
# - ffmpeg: required for Discord voice playback
# - libsndfile1: some audio libs depend on it
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Start your bot
CMD ["python", "-u", "main.py"]
