#!/usr/bin/env python3
"""
Test script to demonstrate the new security agent types in NovaMind AI
"""

import asyncio
import sys
import os

# Add the backend directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.api.endpoints.agents import (
    _run_vulnerability_scanner,
    _run_secure_code_reviewer,
    _run_threat_analyst,
    _run_security_researcher,
    _run_general_agent
)
from app.core.audit_logging import AuditLogger, ImmutableAuditStorage
import tempfile


async def test_security_agents():
    """Test all the new security agent types"""

    # Set up a temporary audit log file for testing
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        temp_log_file = f.name

    try:
        # Initialize audit storage and logger
        storage = ImmutableAuditStorage(temp_log_file)
        audit_logger = AuditLogger(storage)

        print("Testing NovaMind AI Security Agent Types")
        print("=" * 50)

        # Test data
        test_session = {
            "user_id": "test_user_123",
            "task": "Test security assessment for NovaMind AI platform",
            "context": "Internal security review",
            "agent_type": "vulnerability_scanner"  # Will be changed for each test
        }

        # Test each security agent type
        agent_types = [
            ("vulnerability_scanner", _run_vulnerability_scanner),
            ("secure_code_reviewer", _run_secure_code_reviewer),
            ("threat_analyst", _run_threat_analyst),
            ("security_researcher", _run_security_researcher),
            ("general", _run_general_agent)  # For comparison
        ]

        for agent_type_name, agent_function in agent_types:
            print(f"\nTesting {agent_type_name.replace('_', ' ').title()} Agent:")
            print("-" * 40)

            # Update session with current agent type
            test_session["agent_type"] = agent_type_name

            # Run the agent
            result = await agent_function(test_session, audit_logger)

            # Print result summary (first few lines)
            result_lines = result.split('\n')
            for i, line in enumerate(result_lines[:10]):  # Show first 10 lines
                print(line)
            if len(result_lines) > 10:
                print("...")
                print(f"[Result truncated - showing first 10 lines of {len(result_lines)} total lines]")

            print(f"\n{agent_type_name.replace('_', ' ').title()} agent test completed successfully!\n")

        # Show audit log contents
        print("\nAudit Log Contents:")
        print("=" * 30)
        events = await storage.get_events()
        for i, event in enumerate(events):
            print(f"Event {i+1}: {event.action} by {event.user_id} at {event.timestamp}")

    finally:
        # Clean up temporary file
        if os.path.exists(temp_log_file):
            os.unlink(temp_log_file)


if __name__ == "__main__":
    print("Running Security Agents Test...")
    asyncio.run(test_security_agents())
    print("\nTest completed!")