"""Parse task files from different terminal bench formats."""

import toml
import yaml

from app.models.task import EnvironmentConfig, Task, TaskMetadata


class TaskParser:
    """Parse task files into Task objects."""

    @staticmethod
    def parse_yaml(
        task_id: str,
        content: str,
        benchmark: str,
        benchmark_display_name: str,
        github_url: str | None = None,
    ) -> Task:
        """Parse a task.yaml file (Terminal Bench 1 format)."""
        data = yaml.safe_load(content)

        # Remove benchmark canary if present
        instruction = data.get("instruction", "")

        metadata = TaskMetadata(
            author_name=data.get("author_name"),
            author_email=data.get("author_email"),
            difficulty=data.get("difficulty"),
            category=data.get("category"),
            tags=data.get("tags", []),
            expert_time_estimate_min=data.get("expert_time_estimate_min"),
            junior_time_estimate_min=data.get("junior_time_estimate_min"),
        )

        return Task(
            id=task_id,
            benchmark=benchmark,
            benchmark_display_name=benchmark_display_name,
            instruction=instruction,
            metadata=metadata,
            agent_timeout_sec=data.get("max_agent_timeout_sec"),
            verifier_timeout_sec=data.get("max_test_timeout_sec"),
            github_url=github_url,
        )

    @staticmethod
    def parse_toml(
        task_id: str,
        toml_content: str,
        instruction_content: str | None,
        benchmark: str,
        benchmark_display_name: str,
        github_url: str | None = None,
    ) -> Task:
        """Parse a task.toml file with optional instruction.md (Terminal Bench 2/3 format)."""
        data = toml.loads(toml_content)

        # Get metadata section
        meta = data.get("metadata", {})

        metadata = TaskMetadata(
            author_name=meta.get("author_name"),
            author_email=meta.get("author_email"),
            difficulty=meta.get("difficulty"),
            category=meta.get("category"),
            tags=meta.get("tags", []),
            expert_time_estimate_min=meta.get("expert_time_estimate_min"),
            junior_time_estimate_min=meta.get("junior_time_estimate_min"),
        )

        # Get environment section
        env_data = data.get("environment", {})
        environment = None
        if env_data:
            environment = EnvironmentConfig(
                docker_image=env_data.get("docker_image"),
                cpus=env_data.get("cpus"),
                memory=env_data.get("memory"),
                storage=env_data.get("storage"),
                build_timeout_sec=env_data.get("build_timeout_sec"),
            )

        # Get timeouts
        agent_timeout = data.get("agent", {}).get("timeout_sec")
        verifier_timeout = data.get("verifier", {}).get("timeout_sec")

        return Task(
            id=task_id,
            benchmark=benchmark,
            benchmark_display_name=benchmark_display_name,
            instruction=instruction_content or "",
            metadata=metadata,
            environment=environment,
            agent_timeout_sec=agent_timeout,
            verifier_timeout_sec=verifier_timeout,
            github_url=github_url,
        )
