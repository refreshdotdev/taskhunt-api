"""FastAPI application for TaskHunt.ai."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import stats_router, tasks_router

app = FastAPI(
    title="TaskHunt.ai API",
    description="API for exploring Terminal Bench tasks across all benchmarks",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tasks_router)
app.include_router(stats_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "TaskHunt.ai API",
        "version": "0.1.0",
        "description": "Explore Terminal Bench tasks across all benchmarks",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
