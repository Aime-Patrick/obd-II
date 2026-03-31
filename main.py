from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.database import connect_to_mongo, close_mongo_connection
from routes import auth, vehicles, diagnostics, predict

app = FastAPI(
    title="Vehicle Diagnostic AI API",
    description="Smart Vehicle Health Assessment with AI-powered diagnostics",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Events
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

# Routes
app.include_router(predict.router)  # Old endpoint (no auth required)
app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(diagnostics.router)

@app.get("/")
def read_root():
    return {
        "message": "Vehicle Diagnostic AI API v2.0",
        "status": "running",
        "features": ["Authentication", "Vehicle Management", "AI Diagnostics", "Recommendations"]
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
