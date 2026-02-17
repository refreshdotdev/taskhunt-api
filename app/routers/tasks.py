"""Task API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.models.task import Task, TaskListItem
from app.services.pr_fetcher import get_pr_fetcher
from app.services.task_fetcher import get_task_fetcher

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def task_to_list_item(task: Task) -> TaskListItem:
    """Convert a Task to a TaskListItem for list views."""
    instruction_preview = task.instruction[:200] + "..." if len(task.instruction) > 200 else task.instruction
    return TaskListItem(
        id=task.id,
        benchmark=task.benchmark,
        benchmark_display_name=task.benchmark_display_name,
        instruction_preview=instruction_preview,
        difficulty=task.metadata.difficulty,
        category=task.metadata.category,
        tags=task.metadata.tags,
        author_name=task.metadata.author_name,
        is_from_pr=task.pr_info is not None,
        pr_number=task.pr_info.number if task.pr_info else None,
    )


@router.get("", response_model=list[TaskListItem])
async def list_tasks(
    benchmark: str | None = Query(None, description="Filter by benchmark name"),
    difficulty: str | None = Query(None, description="Filter by difficulty"),
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search in task ID and instruction"),
    include_prs: bool = Query(True, description="Include tasks from open PRs"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List all tasks with optional filtering."""
    fetcher = get_task_fetcher()
    pr_fetcher = get_pr_fetcher()

    # Fetch all tasks
    tasks = await fetcher.fetch_all_tasks()

    # Include PR tasks if requested
    if include_prs:
        pr_tasks = await pr_fetcher.fetch_all_pr_tasks()
        tasks = tasks + pr_tasks

    # Apply filters
    if benchmark:
        tasks = [t for t in tasks if t.benchmark == benchmark]

    if difficulty:
        tasks = [t for t in tasks if t.metadata.difficulty == difficulty]

    if category:
        tasks = [t for t in tasks if t.metadata.category == category]

    if search:
        search_lower = search.lower()
        tasks = [
            t
            for t in tasks
            if search_lower in t.id.lower() or search_lower in t.instruction.lower()
        ]

    # Sort by benchmark, then by ID
    tasks = sorted(tasks, key=lambda t: (t.benchmark, t.id))

    # Paginate
    total = len(tasks)
    tasks = tasks[offset : offset + limit]

    # Convert to list items
    return [task_to_list_item(t) for t in tasks]


@router.get("/pr", response_model=list[TaskListItem])
async def list_pr_tasks(
    benchmark: str | None = Query(None, description="Filter by benchmark name"),
    pr_number: int | None = Query(None, description="Filter by PR number"),
):
    """List tasks from open pull requests."""
    pr_fetcher = get_pr_fetcher()
    tasks = await pr_fetcher.fetch_all_pr_tasks()

    if benchmark:
        tasks = [t for t in tasks if t.benchmark == benchmark]

    if pr_number:
        tasks = [t for t in tasks if t.pr_info and t.pr_info.number == pr_number]

    return [task_to_list_item(t) for t in tasks]


@router.get("/{benchmark}/{task_id}", response_model=Task)
async def get_task(benchmark: str, task_id: str):
    """Get a specific task by benchmark and ID."""
    fetcher = get_task_fetcher()
    pr_fetcher = get_pr_fetcher()

    # First check merged tasks
    task = await fetcher.fetch_task_by_id(benchmark, task_id)
    if task:
        return task

    # Then check PR tasks
    pr_tasks = await pr_fetcher.fetch_all_pr_tasks()
    for task in pr_tasks:
        if task.benchmark == benchmark and task.id == task_id:
            return task

    raise HTTPException(status_code=404, detail=f"Task {task_id} not found in {benchmark}")


@router.get("/search", response_model=list[TaskListItem])
async def search_tasks(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
):
    """Search tasks by ID, instruction, or metadata."""
    fetcher = get_task_fetcher()
    pr_fetcher = get_pr_fetcher()

    # Fetch all tasks including PRs
    tasks = await fetcher.fetch_all_tasks()
    pr_tasks = await pr_fetcher.fetch_all_pr_tasks()
    all_tasks = tasks + pr_tasks

    # Search
    q_lower = q.lower()
    results = []
    for task in all_tasks:
        score = 0
        # Exact ID match
        if q_lower == task.id.lower():
            score = 100
        # ID contains query
        elif q_lower in task.id.lower():
            score = 50
        # Instruction contains query
        elif q_lower in task.instruction.lower():
            score = 25
        # Category or tags match
        elif task.metadata.category and q_lower in task.metadata.category.lower():
            score = 20
        elif any(q_lower in tag.lower() for tag in task.metadata.tags):
            score = 15

        if score > 0:
            results.append((score, task))

    # Sort by score (descending)
    results.sort(key=lambda x: x[0], reverse=True)

    # Return top results
    return [task_to_list_item(t) for _, t in results[:limit]]
