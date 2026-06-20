"""
Test script to verify that all the new modules can be imported correctly
"""
print("Testing imports...")

try:
    # Test core modules
    from backend.app.core.speech_service import SpeechService, WhisperSpeechService, SpeechServiceFactory, speech_to_text, text_to_speech
    print("✓ Speech service imports successful")
except Exception as e:
    print(f"✗ Speech service imports failed: {e}")

try:
    from backend.app.core.reasoning_service import ReasoningService, ReasoningStrategy, ReasoningResult, apply_reasoning
    print("✓ Reasoning service imports successful")
except Exception as e:
    print(f"✗ Reasoning service imports failed: {e}")

try:
    from backend.app.core.security_execution import (
        SecurityExecutor, DockerSecurityExecutor, ProcessSecurityExecutor,
        SecurityExecutorFactory, SecurityToolExecutor, create_security_tool_executor,
        secure_execute, ExecutionResult, ExecutionStatus
    )
    print("✓ Security execution imports successful")
except Exception as e:
    print(f"✗ Security execution imports failed: {e}")

try:
    from backend.app.core.audit_logging import (
        AuditLogger, AuditEvent, AuditLevel, AuditStorage, ImmutableAuditStorage,
        init_audit_logger, get_audit_logger, log_audit_event,
        log_authentication_event, log_agent_execution_event, log_security_scan_event,
        log_tool_execution_event, log_data_access_event, log_configuration_change_event
    )
    print("✓ Audit logging imports successful")
except Exception as e:
    print(f"✗ Audit logging imports failed: {e}")

try:
    # Test that we can import from the __init__.py files
    from backend.app.core import (
        SpeechService, WhisperSpeechService, SpeechServiceFactory, speech_to_text, text_to_speech,
        ReasoningService, ReasoningStrategy, ReasoningResult, apply_reasoning,
        SecurityExecutor, DockerSecurityExecutor, ProcessSecurityExecutor,
        SecurityExecutorFactory, SecurityToolExecutor, create_security_tool_executor,
        secure_execute, ExecutionResult, ExecutionStatus,
        AuditLogger, AuditEvent, AuditLevel, AuditStorage, ImmutableAuditStorage,
        init_audit_logger, get_audit_logger, log_audit_event,
        log_authentication_event, log_agent_execution_event, log_security_scan_event,
        log_tool_execution_event, log_data_access_event, log_configuration_change_event
    )
    print("✓ Core module imports successful")
except Exception as e:
    print(f"✗ Core module imports failed: {e}")

print("Import testing complete!")