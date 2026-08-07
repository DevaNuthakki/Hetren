from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.config import get_settings
from app.routes import router
from app.runner_operations_routes import (
    router as runner_operations_router,
)
from app.runner_routes import router as runner_router

settings = get_settings()

app = FastAPI(
    title="Hetren API",
    description="GitHub-native speech AI regression debugging API for ASR evaluation.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(runner_router)
app.include_router(runner_operations_router)


@app.get("/")
def root():
    return {
        "message": "Hetren backend is running",
        "version": "0.1.0",
    }