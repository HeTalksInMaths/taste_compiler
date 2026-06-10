"""Custom exception classes for agentbattery."""


class AgentBatteryError(Exception):
    """Base exception for agentbattery."""


class ScanError(AgentBatteryError):
    """Target path invalid or inaccessible."""


class ContractError(AgentBatteryError):
    """Contract file invalid or missing."""


class ReportError(AgentBatteryError):
    """Cannot write report output."""
