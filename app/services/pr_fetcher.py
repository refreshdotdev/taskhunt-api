"""Fetch tasks from open pull requests with ETag-based caching."""

import asyncio
import base64
import logging

import httpx

from app.config import BENCHMARKS, BenchmarkConfig, settings
from app.models.task import PRInfo, Task
from app.services.cache import get_cache
from app.services.task_parser import TaskParser

logger = logging.getLogger(__name__)


class PRFetcher:
    """Fetch tasks from open pull requests."""

    def __init__(self):
        self.parser = TaskParser()
        self.cache = get_cache()
        self._cache_ttl = settings.cache_ttl_seconds

    def _get_headers(self, etag: str | None = None) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def _parse_github_url(self, url: str) -> tuple[str, str]:
        """Parse owner and repo from GitHub URL."""
        parts = url.rstrip("/").split("/")
        return parts[-2], parts[-1]

    async def _fetch_open_prs(
        self, client: httpx.AsyncClient, owner: str, repo: str
    ) -> list[dict]:
        """Fetch open pull requests from a repository with ETag caching."""
        cache_key = f"prs:{owner}/{repo}"
        cached_entry = self.cache.get(cache_key)
        etag = cached_entry.etag if cached_entry else None

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        params = {"state": "open", "per_page": 50}

        response = await client.get(url, params=params, headers=self._get_headers(etag))

        if response.status_code == 304:
            # Not modified - use cached data
            self.cache.touch(cache_key)
            logger.info(f"Cache hit (304): {cache_key}")
            return cached_entry.data if cached_entry else []

        if response.status_code == 404:
            return []

        response.raise_for_status()

        # Cache the response with ETag
        data = response.json()
        new_etag = response.headers.get("ETag")
        self.cache.set(cache_key, data, new_etag)
        logger.info(f"Cache updated: {cache_key}")

        return data

    async def _fetch_pr_files(
        self, client: httpx.AsyncClient, owner: str, repo: str, pr_number: int
    ) -> list[dict]:
        """Fetch files changed in a PR with ETag caching."""
        cache_key = f"pr_files:{owner}/{repo}/{pr_number}"
        cached_entry = self.cache.get(cache_key)
        etag = cached_entry.etag if cached_entry else None

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"

        response = await client.get(url, headers=self._get_headers(etag))

        if response.status_code == 304:
            self.cache.touch(cache_key)
            return cached_entry.data if cached_entry else []

        if response.status_code == 404:
            return []

        response.raise_for_status()

        data = response.json()
        new_etag = response.headers.get("ETag")
        self.cache.set(cache_key, data, new_etag)

        return data

    async def _fetch_file_content(
        self, client: httpx.AsyncClient, owner: str, repo: str, path: str, ref: str
    ) -> str | None:
        """Fetch content of a file from a specific ref with ETag caching."""
        cache_key = f"file:{owner}/{repo}/{path}@{ref}"
        cached_entry = self.cache.get(cache_key)
        etag = cached_entry.etag if cached_entry else None

        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref}

        response = await client.get(url, params=params, headers=self._get_headers(etag))

        if response.status_code == 304:
            self.cache.touch(cache_key)
            return cached_entry.data if cached_entry else None

        if response.status_code == 404:
            return None

        response.raise_for_status()

        data = response.json()
        content = None
        if data.get("encoding") == "base64":
            content = base64.b64decode(data["content"]).decode("utf-8")
        else:
            content = data.get("content")

        new_etag = response.headers.get("ETag")
        self.cache.set(cache_key, content, new_etag)

        return content

    def _extract_task_ids_from_files(
        self, files: list[dict], benchmark: BenchmarkConfig
    ) -> set[str]:
        """Extract task IDs from PR file changes."""
        task_ids = set()
        prefix = f"{benchmark.tasks_path}/" if benchmark.tasks_path else ""

        for file in files:
            filename = file.get("filename", "")
            if not filename.startswith(prefix):
                continue

            # Remove prefix and get task ID (first path component after prefix)
            relative_path = filename[len(prefix) :]
            parts = relative_path.split("/")
            if len(parts) >= 1 and parts[0]:
                task_ids.add(parts[0])

        return task_ids

    async def _fetch_tasks_from_pr(
        self,
        client: httpx.AsyncClient,
        benchmark: BenchmarkConfig,
        pr: dict,
    ) -> list[Task]:
        """Fetch tasks added/modified in a PR."""
        tasks = []
        owner, repo = self._parse_github_url(benchmark.github_url)

        # Get files changed in PR
        files = await self._fetch_pr_files(client, owner, repo, pr["number"])

        # Extract task IDs from file paths
        task_ids = self._extract_task_ids_from_files(files, benchmark)

        if not task_ids:
            return []

        # Create PR info
        pr_info = PRInfo(
            number=pr["number"],
            title=pr["title"],
            url=pr["html_url"],
            author=pr["user"]["login"],
            state=pr["state"],
            created_at=pr.get("created_at"),
            updated_at=pr.get("updated_at"),
        )

        # Get the PR branch ref
        pr_ref = pr["head"]["ref"]

        # Fetch each task
        for task_id in task_ids:
            try:
                task_path = (
                    f"{benchmark.tasks_path}/{task_id}"
                    if benchmark.tasks_path
                    else task_id
                )

                if benchmark.task_format == "yaml":
                    yaml_path = f"{task_path}/task.yaml"
                    content = await self._fetch_file_content(
                        client, owner, repo, yaml_path, pr_ref
                    )
                    if content:
                        github_url = f"{benchmark.github_url}/pull/{pr['number']}/files"
                        task = self.parser.parse_yaml(
                            task_id=task_id,
                            content=content,
                            benchmark=benchmark.name,
                            benchmark_display_name=benchmark.display_name,
                            github_url=github_url,
                        )
                        task.pr_info = pr_info
                        tasks.append(task)
                else:
                    toml_path = f"{task_path}/task.toml"
                    instruction_path = f"{task_path}/instruction.md"

                    toml_content, instruction_content = await asyncio.gather(
                        self._fetch_file_content(client, owner, repo, toml_path, pr_ref),
                        self._fetch_file_content(
                            client, owner, repo, instruction_path, pr_ref
                        ),
                    )

                    if toml_content:
                        github_url = f"{benchmark.github_url}/pull/{pr['number']}/files"
                        task = self.parser.parse_toml(
                            task_id=task_id,
                            toml_content=toml_content,
                            instruction_content=instruction_content,
                            benchmark=benchmark.name,
                            benchmark_display_name=benchmark.display_name,
                            github_url=github_url,
                        )
                        task.pr_info = pr_info
                        tasks.append(task)

            except Exception as e:
                logger.warning(f"Failed to fetch PR task {task_id}: {e}")

        return tasks

    async def _fetch_pr_tasks_from_benchmark(
        self, client: httpx.AsyncClient, benchmark: BenchmarkConfig
    ) -> list[Task]:
        """Fetch all PR tasks from a single benchmark."""
        owner, repo = self._parse_github_url(benchmark.github_url)

        # Get open PRs
        prs = await self._fetch_open_prs(client, owner, repo)

        if not prs:
            return []

        # Fetch tasks from each PR
        semaphore = asyncio.Semaphore(5)

        async def fetch_pr_tasks(pr: dict) -> list[Task]:
            async with semaphore:
                return await self._fetch_tasks_from_pr(client, benchmark, pr)

        results = await asyncio.gather(*[fetch_pr_tasks(pr) for pr in prs])

        # Flatten results
        all_tasks = []
        for task_list in results:
            all_tasks.extend(task_list)

        return all_tasks

    async def fetch_all_pr_tasks(self, use_cache: bool = True) -> list[Task]:
        """Fetch tasks from all open PRs across all benchmarks."""
        cache_key = "all_pr_tasks"

        # Check if we have fresh cached tasks
        if use_cache:
            cached_entry = self.cache.get(cache_key)
            if cached_entry and self.cache.is_fresh(cache_key, self._cache_ttl):
                logger.info("Returning cached PR tasks (TTL fresh)")
                return cached_entry.data

        async with httpx.AsyncClient(timeout=30.0) as client:
            results = await asyncio.gather(
                *[self._fetch_pr_tasks_from_benchmark(client, b) for b in BENCHMARKS],
                return_exceptions=True,
            )

            all_tasks = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch PRs from {BENCHMARKS[i].name}: {result}")
                else:
                    all_tasks.extend(result)

        # Update cache
        self.cache.set(cache_key, all_tasks)

        return all_tasks


# Singleton instance
_fetcher: PRFetcher | None = None


def get_pr_fetcher() -> PRFetcher:
    """Get the PR fetcher singleton."""
    global _fetcher
    if _fetcher is None:
        _fetcher = PRFetcher()
    return _fetcher
