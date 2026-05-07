FROM python:3.10-slim

# Hugging Face Spaces requires a non-root user with uid 1000
RUN useradd -m -u 1000 user

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and give ownership to the new user
COPY --chown=user:user . /app

# Switch to the "user"
USER user

# Ensure data directory exists for SQLite
RUN mkdir -p data

# Hugging Face Spaces expects the app to run on port 7860
EXPOSE 7860

# Start the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
