FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for scikit-learn and other packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

# Train the model if not present
RUN if [ ! -f "ml/obd_model.joblib" ]; then \
    echo "Training ML model..." && \
    python ml/train_model.py; \
    fi

EXPOSE ${PORT:-8001}

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}"]
