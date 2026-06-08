from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.database import connect_to_mongo, close_mongo_connection, db
from config.settings import settings
from routes import auth, vehicles, diagnostics, predict, admin, admin_auth
from services import ml_model, admin_key_service, system_settings_service, admin_user_service
from services import scheduler_service

app = FastAPI(
    title="SmartDriveX API",
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
    if db.client is not None:
        database = db.client[settings.DATABASE_NAME]
        await system_settings_service.ensure_defaults(database)
        await admin_user_service.ensure_admin_user(database)
        bootstrap = (settings.ADMIN_BOOTSTRAP_KEY or settings.ADMIN_API_KEY or "").strip()
        if bootstrap:
            created = await admin_key_service.seed_bootstrap_key(
                database, bootstrap, label="Bootstrap key (from env)"
            )
            if created:
                print("Seeded admin API key from ADMIN_BOOTSTRAP_KEY / ADMIN_API_KEY into MongoDB.")
        else:
            plain = await admin_key_service.seed_dev_key_if_empty(database)
            if plain:
                print("\n=== AUTO-GENERATED ADMIN API KEY (save to admin-dashboard/.env.local) ===")
                print(plain)
                print("=======================================================================\n")
    try:
        ml_model.ensure_loaded()
    except Exception:
        pass
    scheduler_service.start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler_service.stop_scheduler()
    await close_mongo_connection()

# Routes
app.include_router(predict.router)  # Old endpoint (no auth required)
app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(diagnostics.router)
app.include_router(admin_auth.router)
app.include_router(admin.router)

@app.get("/")
def read_root():
    return {
        "message": "SmartDriveX API v2.0",
        "status": "running",
        "features": ["Authentication", "Vehicle Management", "AI Diagnostics", "Recommendations"]
    }

@app.get("/health")
def health_check():
    try:
        model_info = ml_model.get_info()
    except Exception:
        model_info = {"model_version": None, "status": "not_loaded"}
    return {"status": "healthy", "model": model_info}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
