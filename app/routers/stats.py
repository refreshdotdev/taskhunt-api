"""Statistics API endpoints."""

from collections import defaultdict

from fastapi import APIRouter

from app.models.task import BenchmarkStats, OverallStats
from app.services.pr_fetcher import get_pr_fetcher
from app.services.task_fetcher import get_task_fetcher

router = APIRouter(prefix="/api/stats", tags=["statistics"])


@router.get("", response_model=OverallStats)
async def get_stats():
    """Get overall statistics across all benchmarks."""
    fetcher = get_task_fetcher()
    pr_fetcher = get_pr_fetcher()

    tasks = await fetcher.fetch_all_tasks()
    pr_tasks = await pr_fetcher.fetch_all_pr_tasks()

    # Group tasks by benchmark
    by_benchmark: dict[str, list] = defaultdict(list)
    for task in tasks:
        by_benchmark[task.benchmark].append(task)

    # Collect unique difficulties and categories
    all_difficulties: set[str] = set()
    all_categories: set[str] = set()

    benchmark_stats = []
    for benchmark_name, benchmark_tasks in by_benchmark.items():
        by_difficulty: dict[str, int] = defaultdict(int)
        by_category: dict[str, int] = defaultdict(int)

        display_name = benchmark_tasks[0].benchmark_display_name if benchmark_tasks else benchmark_name

        for task in benchmark_tasks:
            if task.metadata.difficulty:
                by_difficulty[task.metadata.difficulty] += 1
                all_difficulties.add(task.metadata.difficulty)
            if task.metadata.category:
                by_category[task.metadata.category] += 1
                all_categories.add(task.metadata.category)

        benchmark_stats.append(
            BenchmarkStats(
                benchmark=benchmark_name,
                display_name=display_name,
                total_tasks=len(benchmark_tasks),
                by_difficulty=dict(by_difficulty),
                by_category=dict(by_category),
            )
        )

    # Sort benchmark stats by name
    benchmark_stats.sort(key=lambda x: x.benchmark)

    return OverallStats(
        total_tasks=len(tasks),
        total_pr_tasks=len(pr_tasks),
        benchmarks=benchmark_stats,
        difficulties=sorted(all_difficulties),
        categories=sorted(all_categories),
    )


@router.get("/benchmarks", response_model=list[BenchmarkStats])
async def get_benchmark_stats():
    """Get per-benchmark statistics."""
    stats = await get_stats()
    return stats.benchmarks
