"""Fetch tasks from GitHub repositories."""

import asyncio
import base64
import logging
from functools import lru_cache
from time import time

import httpx

from app.config import BENCHMARKS, BenchmarkConfig, settings
from app.models.task import Task
from app.services.task_parser import TaskParser

logger = logging.getLogger(__name__)


class TaskFetcher:
    """Fetch tasks from terminal bench repositories."""

    def __init__(self):
        self.parser = TaskParser()
        self._cache: dict[str, tuple[float, list[Task]]] = {}
        self._cache_ttl = settings.cache_ttl_seconds

    def _get_headers(self) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"
        return headers

    async def _fetch_directory_contents(
        self, client: httpx.AsyncClient, owner: str, repo: str, path: str, branch: str
    ) -> list[dict]:
        """Fetch contents of a directory from GitHub."""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": branch}

        response = await client.get(url, params=params, headers=self._get_headers())
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()

    async def _fetch_file_content(
        self, client: httpx.AsyncClient, owner: str, repo: str, path: str, branch: str
    ) -> str | None:
        """Fetch content of a file from GitHub."""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": branch}

        response = await client.get(url, params=params, headers=self._get_headers())
        if response.status_code == 404:
            return None
        response.raise_for_status()

        data = response.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")
        return data.get("content")

    def _parse_github_url(self, url: str) -> tuple[str, str]:
        """Parse owner and repo from GitHub URL."""
        # Handle URLs like https://github.com/owner/repo
        parts = url.rstrip("/").split("/")
        return parts[-2], parts[-1]

    async def _fetch_tasks_from_benchmark(
        self, client: httpx.AsyncClient, benchmark: BenchmarkConfig
    ) -> list[Task]:
        """Fetch all tasks from a single benchmark."""
        tasks = []
        owner, repo = self._parse_github_url(benchmark.github_url)

        # Get list of task directories
        contents = await self._fetch_directory_contents(
            client, owner, repo, benchmark.tasks_path, benchmark.branch
        )

        # Filter to only directories (potential task folders)
        task_dirs = [item for item in contents if item["type"] == "dir"]

        # Fetch tasks in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(10)

        async def fetch_task(task_dir: dict) -> Task | None:
            async with semaphore:
                task_id = task_dir["name"]
                task_path = (
                    f"{benchmark.tasks_path}/{task_id}"
                    if benchmark.tasks_path
                    else task_id
                )

                try:
                    if benchmark.task_format == "yaml":
                        # Terminal Bench 1 format
                        yaml_path = f"{task_path}/task.yaml"
                        content = await self._fetch_file_content(
                            client, owner, repo, yaml_path, benchmark.branch
                        )
                        if content:
                            github_url = f"{benchmark.github_url}/tree/{benchmark.branch}/{task_path}"
                            return self.parser.parse_yaml(
                                task_id=task_id,
                                content=content,
                                benchmark=benchmark.name,
                                benchmark_display_name=benchmark.display_name,
                                github_url=github_url,
                            )
                    else:
                        # Terminal Bench 2/3 format (toml)
                        toml_path = f"{task_path}/task.toml"
                        instruction_path = f"{task_path}/instruction.md"

                        toml_content, instruction_content = await asyncio.gather(
                            self._fetch_file_content(
                                client, owner, repo, toml_path, benchmark.branch
                            ),
                            self._fetch_file_content(
                                client, owner, repo, instruction_path, benchmark.branch
                            ),
                        )

                        if toml_content:
                            github_url = f"{benchmark.github_url}/tree/{benchmark.branch}/{task_path}"
                            return self.parser.parse_toml(
                                task_id=task_id,
                                toml_content=toml_content,
                                instruction_content=instruction_content,
                                benchmark=benchmark.name,
                                benchmark_display_name=benchmark.display_name,
                                github_url=github_url,
                            )
                except Exception as e:
                    logger.warning(f"Failed to fetch task {task_id}: {e}")

                return None

        results = await asyncio.gather(*[fetch_task(td) for td in task_dirs])
        tasks = [t for t in results if t is not None]

        return tasks

    async def fetch_all_tasks(self, use_cache: bool = True) -> list[Task]:
        """Fetch tasks from all benchmarks."""
        cache_key = "all_tasks"

        # Check cache
        if use_cache and cache_key in self._cache:
            cached_time, cached_tasks = self._cache[cache_key]
            if time() - cached_time < self._cache_ttl:
                return cached_tasks

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch from all benchmarks in parallel
            results = await asyncio.gather(
                *[self._fetch_tasks_from_benchmark(client, b) for b in BENCHMARKS],
                return_exceptions=True,
            )

            all_tasks = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch from {BENCHMARKS[i].name}: {result}")
                else:
                    all_tasks.extend(result)

        # Update cache
        self._cache[cache_key] = (time(), all_tasks)

        return all_tasks

    async def fetch_task_by_id(self, benchmark: str, task_id: str) -> Task | None:
        """Fetch a specific task by benchmark and ID."""
        tasks = await self.fetch_all_tasks()
        for task in tasks:
            if task.benchmark == benchmark and task.id == task_id:
                return task
        return None


# Singleton instance
_fetcher: TaskFetcher | None = None


def get_task_fetcher() -> TaskFetcher:
    """Get the task fetcher singleton."""
    global _fetcher
    if _fetcher is None:
        _fetcher = TaskFetcher()
    return _fetcher
