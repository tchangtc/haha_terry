"""Docker sandbox - isolated execution environment for untrusted tools.

Provides container-based isolation for bash commands and file operations,
preventing access to the host filesystem and network by default.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class DockerSandbox:
    """Isolated execution via Docker containers.

    When enabled, bash commands run inside ephemeral containers
    with strict resource limits and no host filesystem access.
    """

    DEFAULT_IMAGE = "python:3.12-slim"
    DEFAULT_TIMEOUT = 120
    DEFAULT_MEMORY = "512m"
    DEFAULT_CPU = "1.0"

    def __init__(
        self,
        image: str | None = None,
        workdir: Path | None = None,
    ):
        self.image = image or self.DEFAULT_IMAGE
        self.workdir = workdir or Path.cwd()
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if Docker is available."""
        if self._available is None:
            try:
                result = subprocess.run(
                    ["docker", "info"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self._available = result.returncode == 0
            except Exception:
                self._available = False
        return self._available

    def run_command(
        self,
        command: str,
        timeout: int = DEFAULT_TIMEOUT,
        memory: str = DEFAULT_MEMORY,
        cpu: str = DEFAULT_CPU,
        network: bool = False,
        mount_workdir: bool = True,
    ) -> str:
        """Run a command inside a Docker container.

        Args:
            command: Shell command to execute
            timeout: Max execution time in seconds
            memory: Memory limit (e.g., '512m')
            cpu: CPU limit (e.g., '1.0')
            network: Allow network access
            mount_workdir: Mount the working directory

        Returns:
            Command output (stdout + stderr)
        """
        if not self.is_available():
            return "Error: Docker is not available"

        try:
            docker_cmd = [
                "docker", "run", "--rm",
                f"--memory={memory}",
                f"--cpus={cpu}",
                "--network", "none" if not network else "bridge",
                "--workdir", "/workspace",
            ]

            # Mount working directory as read-only
            if mount_workdir:
                docker_cmd.extend([
                    "-v", f"{self.workdir}:/workspace:ro",
                ])

            # Create a writable temp directory
            with tempfile.TemporaryDirectory() as tmpdir:
                docker_cmd.extend([
                    "-v", f"{tmpdir}:/tmp:rw",
                ])

                docker_cmd.extend([
                    self.image,
                    "/bin/sh", "-c", command,
                ])

                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )

                output = (result.stdout + result.stderr).strip()

                # Truncate large outputs
                if len(output) > 50000:
                    output = output[:50000] + "\n... (truncated)"

                return output if output else "(no output)"

        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout}s in Docker sandbox"
        except Exception as e:
            return f"Error: {e}"

    def run_isolated(
        self,
        command: str,
        image: str | None = None,
    ) -> str:
        """Run a command in strict isolation (no network, no mounts)."""
        return self.run_command(
            command,
            network=False,
            mount_workdir=False,
            memory="256m",
            timeout=60,
        )

    def pull_image(self, image: str | None = None) -> str:
        """Pull a Docker image."""
        img = image or self.image
        try:
            result = subprocess.run(
                ["docker", "pull", img],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return (result.stdout + result.stderr).strip()
        except Exception as e:
            return f"Error pulling image {img}: {e}"
