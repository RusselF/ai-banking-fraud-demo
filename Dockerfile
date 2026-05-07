FROM python:3.10-slim

# Hugging Face Spaces requires a non-root user with uid 1000
RUN useradd -m -u 1000 user

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . /app

# Create data dir and change ownership of the entire /app directory to our new user
RUN mkdir -p /app/data && chown -R user:user /app

# Switch to the non-root user
USER user

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
