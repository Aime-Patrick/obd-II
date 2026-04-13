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

# Always retrain the model at build time so it is compatible with the
# exact numpy / scikit-learn versions installed above.
# This avoids "MT19937 is not a known BitGenerator" pickle errors caused
# by loading a .joblib file that was saved on a different numpy version.
RUN python ml/train_model.py

EXPOSE ${PORT:-8001}

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}"]
