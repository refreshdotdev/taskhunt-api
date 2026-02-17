"""Configuration settings for the TaskHunt.ai backend."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class BenchmarkConfig:
    """Configuration for a terminal bench repository."""

    name: str
    display_name: str
    github_url: str
    tasks_path: str
    task_format: str  # "yaml" or "toml"
    branch: str = "main"


BENCHMARKS = [
    BenchmarkConfig(
        name="terminal-bench-1",
        display_name="Terminal Bench (Original)",
        github_url="https://github.com/laude-institute/terminal-bench",
        tasks_path="tasks",
        task_format="yaml",
        branch="main",
    ),
    BenchmarkConfig(
        name="terminal-bench-2",
        display_name="Terminal Bench 2",
        github_url="https://github.com/harbor-framework/terminal-bench-2",
        tasks_path="",  # Tasks are at root
        task_format="toml",
        branch="main",
    ),
    BenchmarkConfig(
        name="terminal-bench-3",
        display_name="Terminal Bench 3 (Community)",
        github_url="https://github.com/harbor-framework/terminal-bench-3",
        tasks_path="tasks",
        task_format="toml",
        branch="main",
    ),
]


@dataclass
class Settings:
    """Application settings."""

    github_token: str | None = None
    cache_ttl_seconds: int = 300  # 5 minutes
    cors_origins: list[str] | None = None

    def __post_init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        default_origins = "http://localhost:5173,http://localhost:3000,https://taskhunt-ai.vercel.app,https://frontend-amber-three-59.vercel.app"
        cors_env = os.getenv("CORS_ORIGINS", default_origins)
        self.cors_origins = [origin.strip() for origin in cors_env.split(",")]


settings = Settings()
