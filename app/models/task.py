"""Task data models."""

from pydantic import BaseModel


class TaskMetadata(BaseModel):
    """Metadata about a task."""

    author_name: str | None = None
    author_email: str | None = None
    difficulty: str | None = None
    category: str | None = None
    tags: list[str] = []
    expert_time_estimate_min: float | None = None
    junior_time_estimate_min: float | None = None


class EnvironmentConfig(BaseModel):
    """Environment configuration for a task."""

    docker_image: str | None = None
    cpus: int | None = None
    memory: str | None = None
    storage: str | None = None
    build_timeout_sec: float | None = None


class PRInfo(BaseModel):
    """Information about a pull request."""

    number: int
    title: str
    url: str
    author: str
    state: str = "open"
    created_at: str | None = None
    updated_at: str | None = None


class Task(BaseModel):
    """A terminal bench task."""

    id: str
    benchmark: str
    benchmark_display_name: str
    instruction: str
    metadata: TaskMetadata
    environment: EnvironmentConfig | None = None
    agent_timeout_sec: float | None = None
    verifier_timeout_sec: float | None = None
    github_url: str | None = None
    pr_info: PRInfo | None = None  # Populated if task is from a PR


class TaskListItem(BaseModel):
    """Condensed task info for list views."""

    id: str
    benchmark: str
    benchmark_display_name: str
    instruction_preview: str  # First ~200 chars
    difficulty: str | None = None
    category: str | None = None
    tags: list[str] = []
    author_name: str | None = None
    is_from_pr: bool = False
    pr_number: int | None = None


class BenchmarkStats(BaseModel):
    """Statistics for a benchmark."""

    benchmark: str
    display_name: str
    total_tasks: int
    by_difficulty: dict[str, int] = {}
    by_category: dict[str, int] = {}


class OverallStats(BaseModel):
    """Overall statistics across all benchmarks."""

    total_tasks: int
    total_pr_tasks: int
    benchmarks: list[BenchmarkStats]
    difficulties: list[str]
    categories: list[str]
