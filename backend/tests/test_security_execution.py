"""
Tests for the security execution service
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from backend.app.core.security_execution import (
    SecurityExecutor,
    DockerSecurityExecutor,
    ProcessSecurityExecutor,
    SecurityExecutorFactory,
    SecurityToolExecutor,
    create_security_tool_executor,
    secure_execute,
    ExecutionResult,
    ExecutionStatus
)

@pytest.mark.asyncio
async def test_security_executor_factory():
    """Test that the security executor factory creates the correct executor type"""
    # Test Docker executor
    docker_executor = SecurityExecutorFactory.create_executor("docker")
    assert isinstance(docker_executor, DockerSecurityExecutor)

    # Test Process executor
    process_executor = SecurityExecutorFactory.create_executor("process")
    assert isinstance(process_executor, ProcessSecurityExecutor)

    # Test default (should try Docker first, then fall back to process)
    default_executor = SecurityExecutorFactory.create_executor()
    # Should be either Docker or Process executor
    assert isinstance(default_executor, (DockerSecurityExecutor, ProcessSecurityExecutor))

@pytest.mark.asyncio
async def test_security_tool_executor_creation():
    """Test creation of security tool executor"""
    # Create a mock executor
    mock_executor = Mock(spec=SecurityExecutor)

    # Create security tool executor
    tool_executor = SecurityToolExecutor(mock_executor)
    assert isinstance(tool_executor, SecurityToolExecutor)
    assert tool_executor.executor == mock_executor

@pytest.mark.asyncio
async def test_create_security_tool_executor():
    """Test the convenience function for creating security tool executor"""
    # This should create a Docker executor by default and wrap it in SecurityToolExecutor
    tool_executor = create_security_tool_executor()
    assert isinstance(tool_executor, SecurityToolExecutor)
    assert isinstance(tool_executor.executor, DockerSecurityExecutor)

    # Test with explicit process executor
    tool_executor_process = create_security_tool_executor(executor_type="process")
    assert isinstance(tool_executor_process, SecurityToolExecutor)
    assert isinstance(tool_executor_process.executor, ProcessSecurityExecutor)

@pytest.mark.asyncio
async def test_docker_security_executor_initialization():
    """Test that Docker security executor initializes with correct parameters"""
    executor = DockerSecurityExecutor(
        default_image="ubuntu:20.04",
        network_disabled=False,
        read_only_root=False,
        mem_limit="1g",
        cpu_quota=100000
    )

    assert executor.default_image == "ubuntu:20.04"
    assert executor.network_disabled == False
    assert executor.read_only_root == False
    assert executor.mem_limit == "1g"
    assert executor.cpu_quota == 100000

@pytest.mark.asyncio
async def test_process_security_executor_initialization():
    """That Process security executor initializes correctly"""
    executor = ProcessSecurityExecutor()
    assert isinstance(executor, ProcessSecurityExecutor)

@pytest.mark.asyncio
async def test_execution_result_dataclass():
    """Test that ExecutionResult dataclass works correctly"""
    result = ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        stdout="Hello, world!",
        stderr="",
        return_code=0,
        execution_time=1.5,
        artifacts={"output.txt": b"Hello, world!"},
        error=None
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert result.stdout == "Hello, world!"
    assert result.stderr == ""
    assert result.return_code == 0
    assert result.execution_time == 1.5
    assert result.artifacts == {"output.txt": b"Hello, world!"}
    assert result.error is None

@pytest.mark.asyncio
async def test_execution_status_enum():
    """Test that ExecutionStatus enum has the expected values"""
    assert ExecutionStatus.PENDING.value == "pending"
    assert ExecutionStatus.RUNNING.value == "running"
    assert ExecutionStatus.COMPLETED.value == "completed"
    assert ExecutionStatus.FAILED.value == "failed"
    assert ExecutionStatus.TIMEOUT.value == "timeout"
    assert ExecutionStatus.KILLED.value == "killed"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])