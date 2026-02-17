"""API routers for TaskHunt.ai."""

from app.routers.stats import router as stats_router
from app.routers.tasks import router as tasks_router

__all__ = ["tasks_router", "stats_router"]
