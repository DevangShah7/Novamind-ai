"""
Secure execution environment for security tools
Provides sandboxed execution to prevent malware and system damage
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import time
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ExecutionStatus(Enum):
    """Status of tool execution"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    KILLED = "killed"

@dataclass
class ExecutionResult:
    """Result of tool execution"""
    status: ExecutionStatus
    stdout: str
    stderr: str
    return_code: Optional[int]
    execution_time: float
    artifacts: Dict[str, Any]  # Files or data generated
    error: Optional[str] = None

class SecurityExecutor(ABC):
    """Abstract base class for secure executors"""

    @abstractmethod
    async def execute(self, command: List[str],
                     input_data: Optional[str] = None,
                     timeout: float = 30.0,
                     work_dir: Optional[str] = None,
                     env: Optional[Dict[str, str]] = None,
                     file_mapping: Optional[Dict[str, str]] = None) -> ExecutionResult:
        """
        Execute a command in a secure environment

        Args:
            command: Command and arguments to execute
            input_data: Optional input data to provide via stdin
            timeout: Maximum execution time in seconds
            work_dir: Working directory for execution
            env: Environment variables
            file_mapping: Mapping of host paths to container paths

        Returns:
            ExecutionResult with stdout, stderr, return code, etc.
        """
        pass

class DockerSecurityExecutor(SecurityExecutor):
    """Secure execution using Docker containers"""

    def __init__(self,
                 default_image: str = "python:3.9-slim",
                 network_disabled: bool = True,
                 read_only_root: bool = True,
                 mem_limit: str = "512m",
                 cpu_quota: int = 50000):  # 50% of one CPU
        """
        Initialize Docker security executor

        Args:
            default_image: Default Docker image to use
            network_disabled: Whether to disable networking
            read_only_root: Whether to mount root filesystem as read-only
            mem_limit: Memory limit (e.g., "512m", "1g")
            cpu_quota: CPU quota in microseconds (default 50% of one CPU)
        """
        self.default_image = default_image
        self.network_disabled = network_disabled
        self.read_only_root = read_only_root
        self.mem_limit = mem_limit
        self.cpu_quota = cpu_quota
        self.logger = logging.getLogger(__name__ + ".DockerSecurityExecutor")

    async def execute(self, command: List[str],
                     input_data: Optional[str] = None,
                     timeout: float = 30.0,
                     work_dir: Optional[str] = None,
                     env: Optional[Dict[str, str]] = None,
                     file_mapping: Optional[Dict[str, str]] = None) -> ExecutionResult:
        """
        Execute command in a Docker container with security restrictions
        """
        start_time = time.time()

        # Prepare Docker run command
        docker_cmd = ["docker", "run", "--rm"]  # Remove container after execution

        # Security restrictions
        if self.network_disabled:
            docker_cmd.append("--network=none")

        if self.read_only_root:
            docker_cmd.append("--read-only")

        # Resource limits
        docker_cmd.extend(["--memory", self.mem_limit])
        docker_cmd.extend(["--cpu-quota", str(self.cpu_quota)])

        # Work directory
        if work_dir:
            docker_cmd.extend(["-w", work_dir])
        else:
            # Create a temporary directory for work
            work_dir = tempfile.mkdtemp(prefix="nova_sec_")
            docker_cmd.extend(["-w", work_dir])

        # Environment variables
        if env:
            for key, value in env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

        # File mappings (volume mounts)
        if file_mapping:
            for host_path, container_path in file_mapping.items():
                # Ensure host path exists
                if os.path.exists(host_path):
                    docker_cmd.extend(["-v", f"{host_path}:{container_path}"])
                else:
                    self.logger.warning(f"Host path does not exist: {host_path}")

        # Image and command
        docker_cmd.append(self.default_image)
        docker_cmd.extend(command)

        self.logger.info(f"Executing in Docker: {' '.join(docker_cmd)}")

        try:
            # Execute the Docker command
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdin=subprocess.PIPE if input_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Handle input data
            stdin_data = input_data.encode('utf-8') if input_data else None

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=stdin_data),
                    timeout=timeout
                )

                execution_time = time.time() - start_time
                return_code = process.returncode

                status = ExecutionStatus.COMPLETED if return_code == 0 else ExecutionStatus.FAILED

                # Collect any generated artifacts
                artifacts = {}
                if work_dir and os.path.exists(work_dir):
                    # Collect files created in the work directory
                    for root, dirs, files in os.walk(work_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, work_dir)
                            try:
                                with open(file_path, 'rb') as f:
                                    artifacts[rel_path] = f.read()
                            except Exception as e:
                                self.logger.warning(f"Could not read artifact {file_path}: {str(e)}")

                # Clean up work directory if we created it
                if work_dir and work_dir.startswith(tempfile.gettempdir()) and "nova_sec_" in work_dir:
                    import shutil
                    shutil.rmtree(work_dir, ignore_errors=True)

                return ExecutionResult(
                    status=status,
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace'),
                    return_code=return_code,
                    execution_time=execution_time,
                    artifacts=artifacts
                )

            except asyncio.TimeoutError:
                # Kill the process on timeout
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass

                return ExecutionResult(
                    status=ExecutionStatus.TIMEOUT,
                    stdout="",
                    stderr="",
                    return_code=None,
                    execution_time=time.time() - start_time,
                    artifacts={},
                    error=f"Execution timed out after {timeout} seconds"
                )

        except Exception as e:
            self.logger.error(f"Error executing Docker command: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                stdout="",
                stderr="",
                return_code=None,
                execution_time=time.time() - start_time,
                artifacts={},
                error=str(e)
            )

class ProcessSecurityExecutor(SecurityExecutor):
    """Secure execution using OS-level process restrictions (fallback when Docker unavailable)"""

    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".ProcessSecurityExecutor")

    async def execute(self, command: List[str],
                     input_data: Optional[str] = None,
                     timeout: float = 30.0,
                     work_dir: Optional[str] = None,
                     env: Optional[Dict[str, str]] = None,
                     file_mapping: Optional[Dict[str, str]] = None) -> ExecutionResult:
        """
        Execute command with OS-level restrictions
        Note: This is less secure than Docker but better than nothing
        """
        start_time = time.time()

        # Prepare work directory
        if work_dir is None:
            work_dir = tempfile.mkdtemp(prefix="nova_sec_")
            cleanup_work_dir = True
        else:
            cleanup_work_dir = False
            # Ensure directory exists
            os.makedirs(work_dir, exist_ok=True)

        try:
            # Prepare environment
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)

            # Change to work directory
            old_cwd = os.getcwd()
            os.chdir(work_dir)

            # Execute the process
            self.logger.info(f"Executing in restricted process: {' '.join(command)}")

            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=subprocess.PIPE if input_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=exec_env
            )

            # Handle input data
            stdin_data = input_data.encode('utf-8') if input_data else None

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=stdin_data),
                    timeout=timeout
                )

                execution_time = time.time() - start_time
                return_code = process.returncode

                status = ExecutionStatus.COMPLETED if return_code == 0 else ExecutionStatus.FAILED

                # Collect any generated artifacts
                artifacts = {}
                if os.path.exists(work_dir):
                    for root, dirs, files in os.walk(work_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, work_dir)
                            try:
                                with open(file_path, 'rb') as f:
                                    artifacts[rel_path] = f.read()
                            except Exception as e:
                                self.logger.warning(f"Could not read artifact {file_path}: {str(e)}")

                return ExecutionResult(
                    status=status,
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace'),
                    return_code=return_code,
                    execution_time=execution_time,
                    artifacts=artifacts
                )

            except asyncio.TimeoutError:
                # Kill the process on timeout
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass

                return ExecutionResult(
                    status=ExecutionStatus.TIMEOUT,
                    stdout="",
                    stderr="",
                    return_code=None,
                    execution_time=time.time() - start_time,
                    artifacts={},
                    error=f"Execution timed out after {timeout} seconds"
                )

        except Exception as e:
            self.logger.error(f"Error executing process: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                stdout="",
                stderr="",
                return_code=None,
                execution_time=time.time() - start_time,
                artifacts={},
                error=str(e)
            )
        finally:
            # Restore working directory
            try:
                os.chdir(old_cwd)
            except Exception:
                pass

            # Clean up work directory if we created it
            if cleanup_work_dir and os.path.exists(work_dir):
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)

class SecurityExecutorFactory:
    """Factory for creating security executor instances"""

    @staticmethod
    def create_executor(executor_type: str = "docker", **kwargs) -> SecurityExecutor:
        """
        Create a security executor instance

        Args:
            executor_type: Type of executor to create ("docker", "process")
            **kwargs: Additional arguments for the executor constructor

        Returns:
            SecurityExecutor instance
        """
        if executor_type.lower() == "docker":
            return DockerSecurityExecutor(**kwargs)
        elif executor_type.lower() == "process":
            return ProcessSecurityExecutor(**kwargs)
        else:
            # Try Docker first, fall back to process
            try:
                return DockerSecurityExecutor(**kwargs)
            except Exception as e:
                logger.warning(f"Failed to create Docker executor, falling back to process: {str(e)}")
                return ProcessSecurityExecutor(**kwargs)

# Convenience functions
async def secure_execute(command: List[str],
                        input_data: Optional[str] = None,
                        timeout: float = 30.0,
                        work_dir: Optional[str] = None,
                        env: Optional[Dict[str, str]] = None,
                        file_mapping: Optional[Dict[str, str]] = None,
                        executor_type: str = "docker",
                        **kwargs) -> ExecutionResult:
    """
    Convenience function for secure execution
    """
    executor = SecurityExecutorFactory.create_executor(executor_type, **kwargs)
    return await executor.execute(command, input_data, timeout, work_dir, env, file_mapping)

# Predefined security tool executors
class SecurityToolExecutor:
    """Executor for common security tools with predefined configurations"""

    def __init__(self, executor: SecurityExecutor):
        self.executor = executor
        self.logger = logging.getLogger(__name__ + ".SecurityToolExecutor")

    async def run_bandit(self, target_path: str,
                        config_file: Optional[str] = None,
                        timeout: float = 60.0) -> ExecutionResult:
        """Run Bandit Python security linter"""
        command = ["bandit", "-r", target_path, "-f", "json"]
        if config_file:
            command.extend(["-c", config_file])

        file_mapping = {}
        if os.path.exists(target_path):
            file_mapping[target_path] = target_path
        if config_file and os.path.exists(config_file):
            file_mapping[config_file] = config_file

        return await self.executor.execute(
            command=command,
            timeout=timeout,
            file_mapping=file_mapping if file_mapping else None
        )

    async def run_semgrep(self, target_path: str,
                         rules: str = "p/r2c",
                         timeout: float = 60.0) -> ExecutionResult:
        """Run Semgrep multi-language security analysis"""
        command = ["semgrep", "--config", rules, "--json", target_path]

        file_mapping = {}
        if os.path.exists(target_path):
            file_mapping[target_path] = target_path

        return await self.executor.execute(
            command=command,
            timeout=timeout,
            file_mapping=file_mapping if file_mapping else None
        )

    async def run_safety(self, requirements_path: str,
                        timeout: float = 30.0) -> ExecutionResult:
        """Run Safety dependency vulnerability scanner"""
        command = ["safety", "check", "-r", requirements_path, "--json"]

        file_mapping = {}
        if os.path.exists(requirements_path):
            file_mapping[requirements_path] = requirements_path

        return await self.executor.execute(
            command=command,
            timeout=timeout,
            file_mapping=file_mapping if file_mapping else None
        )

    async def run_pip_audit(self, requirements_path: str,
                           timeout: float = 30.0) -> ExecutionResult:
        """Run pip-audit dependency vulnerability scanner"""
        command = ["pip-audit", "-r", requirements_path, "--format", "json"]

        file_mapping = {}
        if os.path.exists(requirements_path):
            file_mapping[requirements_path] = requirements_path

        return await self.executor.execute(
            command=command,
            timeout=timeout,
            file_mapping=file_mapping if file_mapping else None
        )

    async def run_trivy_fs(self, target_path: str,
                          timeout: float = 120.0) -> ExecutionResult:
        """Run Trivy filesystem scanner"""
        command = ["trivy", "fs", "--format", "json", target_path]

        file_mapping = {}
        if os.path.exists(target_path):
            file_mapping[target_path] = target_path

        return await self.executor.execute(
            command=command,
            timeout=timeout,
            file_mapping=file_mapping if file_mapping else None
        )

# Factory for security tool executor
def create_security_tool_executor(executor_type: str = "docker", **kwargs) -> SecurityToolExecutor:
    """
    Create a security tool executor instance

    Args:
        executor_type: Type of executor to use ("docker", "process")
        **kwargs: Additional arguments for the executor constructor

    Returns:
        SecurityToolExecutor instance
    """
    executor = SecurityExecutorFactory.create_executor(executor_type, **kwargs)
    return SecurityToolExecutor(executor)