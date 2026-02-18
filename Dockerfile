# ABCover Streamlit app - Docker image
FROM python:3.11-slim

# Avoid buffers so logs show up immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Upgrade pip and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy app code and config
COPY .streamlit/ .streamlit/
COPY app.py auth.py audit.py add_user.py ./
COPY agents/ agents/
COPY abcover_logo.png ./
# raw_data and persistent data dir (for volume mount)
RUN mkdir -p raw_data /app/data

# Streamlit listens on all interfaces so AWS can reach it
EXPOSE 8501

# Run the app via python -m to avoid corrupted streamlit launcher script in container
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
