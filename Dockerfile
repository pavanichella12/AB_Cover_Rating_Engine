# ABCover Streamlit app - Docker image
FROM python:3.11-slim

# Avoid buffers so logs show up immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt streamlit

# Copy app code and config
COPY .streamlit/ .streamlit/
COPY app.py auth.py audit.py add_user.py ./
COPY agents/ agents/
COPY abcover_logo.png ./
COPY ANSWER_KEY_SMALL.csv ./
# raw_data not in repo (large files); create dir for uploads at runtime
RUN mkdir -p raw_data

# Streamlit listens on all interfaces so AWS can reach it
EXPOSE 8501

# Run the app (env vars like GOOGLE_API_KEY must be set when you run the container)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
