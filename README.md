# TaskHunt.ai Backend

Python FastAPI backend for TaskHunt.ai - a platform for exploring Terminal Bench tasks.

## Setup

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload

# Or with plain pip
pip install -e .
uvicorn app.main:app --reload
```

## Environment Variables

- `GITHUB_TOKEN` - GitHub personal access token (optional, increases rate limits)
- `CORS_ORIGINS` - Comma-separated list of allowed origins (default: localhost)

## API Endpoints

### Tasks
- `GET /api/tasks` - List all tasks with filtering
- `GET /api/tasks/pr` - List tasks from open PRs
- `GET /api/tasks/{benchmark}/{task_id}` - Get specific task
- `GET /api/tasks/search?q=` - Search tasks

### Statistics
- `GET /api/stats` - Overall statistics
- `GET /api/stats/benchmarks` - Per-benchmark statistics

## Development

```bash
# Run linter
uv run ruff check .

# Fix linting issues
uv run ruff check . --fix

# Run tests
uv run pytest
```
