#!/bin/bash
# Startup script for SmartDriveX backend
# Trains the ML model if not present, then starts the server

echo "=== SmartDriveX Backend Startup ==="

# Install dependencies
pip install -r requirements.txt

# Train model if not present
if [ ! -f "ml/obd_model.joblib" ]; then
    echo "Model not found. Training..."
    python ml/train_model.py
    echo "Model trained successfully."
else
    echo "Model already exists. Skipping training."
fi

# Start the server
echo "Starting FastAPI server..."
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}
