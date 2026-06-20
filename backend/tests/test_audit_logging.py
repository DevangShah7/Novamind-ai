"""
Tests for the audit logging service
"""
import pytest
import asyncio
import tempfile
import os
import json
from unittest.mock import Mock, AsyncMock
from backend.app.core.audit_logging import (
    AuditLogger,
    AuditEvent,
    AuditLevel,
    AuditStorage,
    ImmutableAuditStorage,
    init_audit_logger,
    get_audit_logger,
    log_audit_event,
    log_authentication_event,
    log_agent_execution_event,
    log_security_scan_event,
    log_tool_execution_event,
    log_data_access_event,
    log_configuration_change_event,
    ExecutionResult,
    ExecutionStatus
)

@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        pass
    yield f.name
    # Cleanup
    if os.path.exists(f.name):
        os.unlink(f.name)

@pytest.mark.asyncio
async def test_immutable_audit_storage_initialization(temp_log_file):
    """Test that immutable audit storage initializes correctly"""
    storage = ImmutableAuditStorage(temp_log_file)
    assert storage.log_file == temp_log_file

@pytest.mark.asyncio
async def test_audit_logger_initialization(temp_log_file):
    """Test that audit logger initializes correctly"""
    storage = ImmutableAuditStorage(temp_log_file)
    logger = AuditLogger(storage)
    assert logger.storage == storage

@pytest.mark.asyncio
async def test_audit_event_dataclass():
    """Test that AuditEvent dataclass works correctly"""
    event = AuditEvent(
        event_id="test-event-123",
        timestamp="2023-01-01T12:00:00Z",
        level=AuditLevel.SECURITY,
        category="authentication",
        action="login_attempt",
        user_id="user123",
        session_id="session456",
        resource="auth_system",
        details={"success": True, "ip_address": "192.168.1.1"},
        metadata={"auth_method": "password"},
        hash_chain="previous-hash",
        signature="test-signature"
    )

    assert event.event_id == "test-event-123"
    assert event.timestamp == "2023-01-01T12:00:00Z"
    assert event.level == AuditLevel.SECURITY
    assert event.category == "authentication"
    assert event.action == "login_attempt"
    assert event.user_id == "user123"
    assert event.session_id == "session456"
    assert event.resource == "auth_system"
    assert event.details == {"success": True, "ip_address": "192.168.1.1"}
    assert event.metadata == {"auth_method": "password"}
    assert event.hash_chain == "previous-hash"
    assert event.signature == "test-signature"

@pytest.mark.asyncio
async def test_audit_level_enum():
    """Test that AuditLevel enum has the expected values"""
    assert AuditLevel.INFO.value == "info"
    assert AuditLevel.WARNING.value == "warning"
    assert AuditLevel.ERROR.value == "error"
    assert AuditLevel.SECURITY.value == "security"
    assert AuditLevel.COMPLIANCE.value == "compliance"

@pytest.mark.asyncio
async def test_immutable_audit_storage_store_event(temp_log_file):
    """Test storing an audit event"""
    storage = ImmutableAuditStorage(temp_log_file)
    logger = AuditLogger(storage)

    # Log an event
    event_id = await logger.log_event(
        level=AuditLevel.INFO,
        category="test",
        action="test_action",
        user_id="test_user",
        details={"test": "data"}
    )

    # Verify that we got an event ID back
    assert isinstance(event_id, str)
    assert len(event_id) > 0

    # Verify that the event was actually stored by reading the log file
    with open(temp_log_file, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 1

        # Parse the event
        event_data = json.loads(lines[0].strip())
        assert event_data['event_id'] == event_id
        assert event_data['category'] == "test"
        assert event_data['action'] == "test_action"
        assert event_data['user_id'] == "test_user"
        assert event_data['details'] == {"test": "data"}

@pytest.mark.asyncio
async def test_immutable_audit_storage_get_events(temp_log_file):
    """Test retrieving audit events"""
    storage = ImmutableAuditStorage(temp_log_file)
    logger = AuditLogger(storage)

    # Log a few events
    await logger.log_event(
        level=AuditLevel.INFO,
        category="test1",
        action="action1",
        user_id="user1",
        details={"test": "data1"}
    )

    await logger.log_event(
        level=AuditLevel.ERROR,
        category="test2",
        action="action2",
        user_id="user2",
        details={"test": "data2"}
    )

    # Retrieve events
    events = await storage.get_events()

    # Should have 2 events
    assert len(events) == 2

    # Check first event
    assert events[0].category == "test1"
    assert events[0].action == "action1"
    assert events[0].user_id == "user1"
    assert events[0].details == {"test": "data1"}

    # Check second event
    assert events[1].category == "test2"
    assert events[1].action == "action2"
    assert events[1].user_id == "user2"
    assert events[1].details == {"test": "data2"}

@pytest.mark.asyncio
async def test_immutable_audit_storage_get_latest_hash(temp_log_file):
    """Test getting the latest hash"""
    storage = ImmutableAuditStorage(temp_log_file)

    # Initially, there should be no hash
    latest_hash = await storage.get_latest_hash()
    assert latest_hash is None

    # Add an event
    logger = AuditLogger(storage)
    await logger.log_event(
        level=AuditLevel.INFO,
        category="test",
        action="test_action",
        user_id="test_user",
        details={"test": "data"}
    )

    # Now there should be a hash
    latest_hash = await storage.get_latest_hash()
    assert latest_hash is not None
    assert isinstance(latest_hash, str)
    assert len(latest_hash) > 0

@pytest.mark.asyncio
async def test_init_audit_logger(temp_log_file):
    """Test the init_audit_logger convenience function"""
    logger = init_audit_logger(temp_log_file)
    assert isinstance(logger, AuditLogger)
    assert isinstance(logger.storage, ImmutableAuditStorage)
    assert logger.storage.log_file == temp_log_file

    # Test that we can log something
    event_id = await logger.log_event(
        level=AuditLevel.INFO,
        category="init_test",
        action="test",
        user_id="test_user"
    )
    assert isinstance(event_id, str)
    assert len(event_id) > 0

@pytest.mark.asyncio
async def test_get_audit_logger_before_init():
    """Test that get_audit_logger raises an error before initialization"""
    # Temporarily unset the global logger
    import backend.app.core.audit_logging as audit_module
    original_logger = audit_module._audit_logger
    audit_module._audit_logger = None

    try:
        with pytest.raises(RuntimeError, match="Audit logger not initialized"):
            get_audit_logger()
    finally:
        # Restore the original logger
        audit_module._audit_logger = original_logger

@pytest.mark.asyncio
async def test_get_audit_logger_after_init(temp_log_file):
    """Test that get_audit_logger works after initialization"""
    # Initialize the logger
    init_audit_logger(temp_log_file)

    # Get the logger
    logger = get_audit_logger()
    assert isinstance(logger, AuditLogger)

    # Test that we can use it
    event_id = await logger.log_event(
        level=AuditLevel.INFO,
        category="get_test",
        action="test",
        user_id="test_user"
    )
    assert isinstance(event_id, str)
    assert len(event_id) > 0

@pytest.mark.asyncio
async def test_convenience_logging_functions(temp_log_file):
    """Test the convenience logging functions"""
    # Initialize the global logger
    init_audit_logger(temp_log_file)

    # Test log_authentication_event
    event_id = await log_authentication_event(
        user_id="test_user",
        action="login_attempt",
        success=True,
        ip_address="192.168.1.100"
    )
    assert isinstance(event_id, str)
    assert len(event_id) > 0

    # Test log_agent_execution_event
    event_id = await log_agent_execution_event(
        agent_id="agent123",
        agent_type="security_scanner",
        action="scan_initiated",
        user_id="test_user",
        details={"target": "192.168.1.0/24"}
    )
    assert isinstance(event_id, str)
    assert len(event_id) > 0

    # Test log_security_scan_event
    event_id = await log_security_scan_event(
        scan_type="vulnerability_scan",
        target="192.168.1.0/24",
        user_id="test_user",
        scan_id="scan456",
        details={"scanner": "nessus"}
    )
    assert isinstance(event_id, str)
    assert len(event_id) > 0

    # Test log_tool_execution_event
    event_id = await log_tool_execution_event(
        tool_name="bandit",
        command=["bandit", "-r", "/app/src"],
        user_id="test_user",
        work_dir="/app/src"
    )
    assert isinstance(event_id, str)
    assert len(event_id) > 0

    # Test log_data_access_event
    event_id = await log_data_access_event(
        user_id="test_user",
        resource="database:users",
        action="read",
        details={"query": "SELECT * FROM users WHERE id = 1"}
    )
    assert isinstance(event_id, str)
    assert len(event_id) > 0

    # Test log_configuration_change_event
    event_id = await log_configuration_change_event(
        user_id="admin_user",
        component="auth_settings",
        change_description="Changed password policy",
        old_value="minimum 8 characters",
        new_value="minimum 12 characters",
        session_id="session789"
    )
    assert isinstance(event_id, str)
    assert len(event_id) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])