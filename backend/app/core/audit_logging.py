"""
Immutable audit logging for security and compliance
Provides tamper-evident logging of security-relevant activities
"""

import logging
import json
import hashlib
import time
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

class AuditLevel(Enum):
    """Audit log levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SECURITY = "security"
    COMPLIANCE = "compliance"

@dataclass
class AuditEvent:
    """Represents an audit event"""
    event_id: str
    timestamp: str
    level: AuditLevel
    category: str
    action: str
    user_id: Optional[str]
    session_id: Optional[str]
    resource: Optional[str]
    details: Dict[str, Any]
    metadata: Dict[str, Any]
    hash_chain: str  # Hash of previous event for tamper evidence
    signature: Optional[str] = None  # Cryptographic signature (if implemented)

class AuditStorage(ABC):
    """Abstract base class for audit storage"""

    @abstractmethod
    async def store_event(self, event: AuditEvent) -> bool:
        """
        Store an audit event

        Args:
            event: The audit event to store

        Returns:
            True if stored successfully, False otherwise
        """
        pass

    @abstractmethod
    async def get_events(self, start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 1000,
                        offset: int = 0) -> List[AuditEvent]:
        """
        Retrieve audit events

        Args:
            start_time: Start time for filtering
            end_time: End time for filtering
            limit: Maximum number of events to return
            offset: Offset for pagination

        Returns:
            List of audit events
        """
        pass

    @abstractmethod
    async def get_latest_hash(self) -> Optional[str]:
        """
        Get the hash of the most recent event for chaining

        Returns:
            Hash string of the latest event, or None if no events
        """
        pass

class ImmutableAuditStorage(AuditStorage):
    """Append-only audit storage with hash chaining for tamper evidence"""

    def __init__(self, log_file: str):
        """
        Initialize audit storage

        Args:
            log_file: Path to the audit log file
        """
        self.log_file = log_file
        self.logger = logging.getLogger(__name__ + ".ImmutableAuditStorage")
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True) if os.path.dirname(log_file) else None

    async def store_event(self, event: AuditEvent) -> bool:
        """Store an audit event with hash chaining"""
        try:
            # Get the hash of the previous event for chaining
            previous_hash = await self.get_latest_hash()
            event.hash_chain = previous_hash or "genesis"

            # Convert event to JSON for storage
            event_json = json.dumps(asdict(event), sort_keys=True, default=str)

            # Append to log file
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(event_json + '\n')

            self.logger.info(f"Stored audit event {event.event_id} in category {event.category}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to store audit event: {str(e)}")
            return False

    async def get_events(self, start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 1000,
                        offset: int = 0) -> List[AuditEvent]:
        """Retrieve audit events with optional time filtering"""
        events = []
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Apply offset
            lines = lines[offset:] if offset < len(lines) else []

            # Apply limit
            lines = lines[:limit] if len(lines) > limit else lines

            # Parse each line
            for line_num, line in enumerate(lines):
                try:
                    event_data = json.loads(line.strip())
                    # Convert timestamp string back to datetime for comparison if needed
                    event = AuditEvent(**event_data)
                    events.append(event)
                except Exception as e:
                    self.logger.warning(f"Failed to parse audit log line {line_num}: {str(e)}")
                    continue

            return events
        except FileNotFoundError:
            self.logger.warning(f"Audit log file not found: {self.log_file}")
            return []
        except Exception as e:
            self.logger.error(f"Error reading audit log: {str(e)}")
            return []

    async def get_latest_hash(self) -> Optional[str]:
        """Get the hash of the most recent event"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines:
                    return None

                # Get the last non-empty line
                for line in reversed(lines):
                    if line.strip():
                        try:
                            event_data = json.loads(line.strip())
                            return event_data.get('hash_chain')
                        except Exception:
                            continue
                return None
        except FileNotFoundError:
            return None
        except Exception as e:
            self.logger.error(f"Error getting latest hash: {str(e)}")
            return None

class AuditLogger:
    """Main audit logging service"""

    def __init__(self, storage: AuditStorage):
        """
        Initialize audit logger

        Args:
            storage: Storage backend for audit events
        """
        self.storage = storage
        self.logger = logging.getLogger(__name__ + ".AuditLogger")

    async def log_event(self, level: AuditLevel, category: str, action: str,
                       user_id: Optional[str] = None, session_id: Optional[str] = None,
                       resource: Optional[str] = None,
                       details: Optional[Dict[str, Any]] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Log an audit event

        Args:
            level: Audit level
            category: Event category (e.g., "authentication", "agent_execution", "security_scan")
            action: Specific action performed
            user_id: ID of the user performing the action
            session_id: Session identifier
            resource: Resource being accessed or modified
            details: Additional details about the event
            metadata: Additional metadata

        Returns:
            Event ID of the logged event
        """
        try:
            # Generate unique event ID
            event_id = str(uuid.uuid4())

            # Create audit event
            event = AuditEvent(
                event_id=event_id,
                timestamp=datetime.utcnow().isoformat() + 'Z',
                level=level,
                category=category,
                action=action,
                user_id=user_id,
                session_id=session_id,
                resource=resource,
                details=details or {},
                metadata=metadata or {},
                hash_chain="",  # Will be filled by storage
                signature=None  # Could be implemented with cryptographic signing
            )

            # Store the event
            success = await self.storage.store_event(event)
            if success:
                self.logger.info(f"Logged audit event {event_id}: {category}/{action}")
                return event_id
            else:
                self.logger.error(f"Failed to store audit event {event_id}")
                raise RuntimeError("Failed to store audit event")

        except Exception as e:
            self.logger.error(f"Error logging audit event: {str(e)}")
            raise

    # Convenience methods for common audit events
    async def log_authentication(self, user_id: str, action: str,
                                success: bool, ip_address: Optional[str] = None,
                                session_id: Optional[str] = None,
                                details: Optional[Dict[str, Any]] = None) -> str:
        """Log authentication-related events"""
        event_details = {
            "success": success,
            "ip_address": ip_address
        }
        if details:
            event_details.update(details)

        return await self.log_event(
            level=AuditLevel.SECURITY if not success else AuditLevel.INFO,
            category="authentication",
            action=action,
            user_id=user_id,
            session_id=session_id,
            resource="auth_system",
            details=event_details
        )

    async def log_agent_execution(self, agent_id: str, agent_type: str,
                                 action: str, user_id: Optional[str] = None,
                                 session_id: Optional[str] = None,
                                 details: Optional[Dict[str, Any]] = None) -> str:
        """Log agent execution events"""
        event_details = {
            "agent_id": agent_id,
            "agent_type": agent_type
        }
        if details:
            event_details.update(details)

        return await self.log_event(
            level=AuditLevel.INFO,
            category="agent_execution",
            action=action,
            user_id=user_id,
            session_id=session_id,
            resource=f"agent:{agent_id}",
            details=event_details
        )

    async def log_security_scan(self, scan_type: str, target: str,
                               user_id: Optional[str] = None,
                               session_id: Optional[str] = None,
                               scan_id: Optional[str] = None,
                               details: Optional[Dict[str, Any]] = None) -> str:
        """Log security scan events"""
        event_details = {
            "scan_type": scan_type,
            "target": target
        }
        if scan_id:
            event_details["scan_id"] = scan_id
        if details:
            event_details.update(details)

        return await self.log_event(
            level=AuditLevel.SECURITY,
            category="security_scan",
            action="scan_initiated",
            user_id=user_id,
            session_id=session_id,
            resource=target,
            details=event_details
        )

    async def log_tool_execution(self, tool_name: str, command: List[str],
                                user_id: Optional[str] = None,
                                session_id: Optional[str] = None,
                                work_dir: Optional[str] = None,
                                details: Optional[Dict[str, Any]] = None) -> str:
        """Log security tool execution events"""
        event_details = {
            "tool_name": tool_name,
            "command": command,
            "work_dir": work_dir
        }
        if details:
            event_details.update(details)

        return await self.log_event(
            level=AuditLevel.SECURITY,
            category="tool_execution",
            action="tool_executed",
            user_id=user_id,
            session_id=session_id,
            resource=tool_name,
            details=event_details
        )

    async def log_data_access(self, user_id: str, resource: str,
                             action: str, session_id: Optional[str] = None,
                             details: Optional[Dict[str, Any]] = None) -> str:
        """Log data access events"""
        return await self.log_event(
            level=AuditLevel.COMPLIANCE,
            category="data_access",
            action=action,
            user_id=user_id,
            session_id=session_id,
            resource=resource,
            details=details or {}
        )

    async def log_configuration_change(self, user_id: str, component: str,
                                      change_description: str,
                                      old_value: Any = None,
                                      new_value: Any = None,
                                      session_id: Optional[str] = None) -> str:
        """Log configuration change events"""
        event_details = {
            "component": component,
            "change_description": change_description,
            "old_value": str(old_value) if old_value is not None else None,
            "new_value": str(new_value) if new_value is not None else None
        }

        return await self.log_event(
            level=AuditLevel.WARNING,
            category="configuration",
            action="configuration_changed",
            user_id=user_id,
            session_id=session_id,
            resource=component,
            details=event_details
        )

# Global audit logger instance (to be initialized in main.py)
_audit_logger: Optional[AuditLogger] = None

def init_audit_logger(log_file: str = "/var/log/novamind/audit.log") -> AuditLogger:
    """
    Initialize the global audit logger

    Args:
        log_file: Path to the audit log file

    Returns:
        The initialized AuditLogger instance
    """
    global _audit_logger
    storage = ImmutableAuditStorage(log_file)
    _audit_logger = AuditLogger(storage)
    logger.info(f"Initialized audit logger with file: {log_file}")
    return _audit_logger

def get_audit_logger() -> AuditLogger:
    """
    Get the global audit logger instance

    Returns:
        The AuditLogger instance

    Raises:
        RuntimeError: If the audit logger has not been initialized
    """
    global _audit_logger
    if _audit_logger is None:
        raise RuntimeError("Audit logger not initialized. Call init_audit_logger() first.")
    return _audit_logger

# Convenience functions using the global logger
async def log_audit_event(level: AuditLevel, category: str, action: str,
                         user_id: Optional[str] = None, session_id: Optional[str] = None,
                         resource: Optional[str] = None,
                         details: Optional[Dict[str, Any]] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to log an audit event using the global logger"""
    return await get_audit_logger().log_event(level, category, action, user_id, session_id, resource, details, metadata)

async def log_authentication_event(user_id: str, action: str, success: bool,
                                  ip_address: Optional[str] = None,
                                  session_id: Optional[str] = None,
                                  details: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to log authentication events"""
    return await get_audit_logger().log_authentication(user_id, action, success, ip_address, session_id, details)

async def log_agent_execution_event(agent_id: str, agent_type: str, action: str,
                                   user_id: Optional[str] = None,
                                   session_id: Optional[str] = None,
                                   details: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to log agent execution events"""
    return await get_audit_logger().log_agent_execution(agent_id, agent_type, action, user_id, session_id, details)

async def log_security_scan_event(scan_type: str, target: str,
                                 user_id: Optional[str] = None,
                                 session_id: Optional[str] = None,
                                 scan_id: Optional[str] = None,
                                 details: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to log security scan events"""
    return await get_audit_logger().log_security_scan(scan_type, target, user_id, session_id, scan_id, details)

async def log_tool_execution_event(tool_name: str, command: List[str],
                                  user_id: Optional[str] = None,
                                  session_id: Optional[str] = None,
                                  work_dir: Optional[str] = None,
                                  details: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to log tool execution events"""
    return await get_audit_logger().log_tool_execution(tool_name, command, user_id, session_id, work_dir, details)

async def log_data_access_event(user_id: str, resource: str,
                                action: str = "read",
                                session_id: Optional[str] = None,
                                details: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to log data access events"""
    return await get_audit_logger().log_data_access(user_id, resource, action, session_id, details)

async def log_configuration_change_event(user_id: str, component: str,
                                         setting: str, old_value: Any = None,
                                         new_value: Any = None,
                                         session_id: Optional[str] = None,
                                         details: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to log configuration change events"""
    return await get_audit_logger().log_configuration_change(user_id, component, setting, old_value, new_value, session_id, details)