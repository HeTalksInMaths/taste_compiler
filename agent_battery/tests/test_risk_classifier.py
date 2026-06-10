"""Unit tests for the risk classifier module."""

from agentbattery.models import RiskLevel, SideEffectLevel, ToolArtifact
from agentbattery.risk_classifier import classify_risk, classify_risk_level, classify_tools


class TestRiskClassifier:
    """Tests for classify_risk and classify_risk_level functions."""

    def test_send_email_external_write_high(self):
        """send_email → EXTERNAL_WRITE, HIGH."""
        tool = ToolArtifact(
            name="send_email",
            description="Send an email to a recipient.",
            source_path="tools/email.py",
        )
        assert classify_risk(tool) == SideEffectLevel.EXTERNAL_WRITE
        assert classify_risk_level(tool) == RiskLevel.HIGH

    def test_issue_refund_external_write_critical(self):
        """issue_refund → EXTERNAL_WRITE, CRITICAL (financial)."""
        tool = ToolArtifact(
            name="issue_refund",
            description="Issue a refund to the customer's account.",
            source_path="tools/payments.py",
        )
        assert classify_risk(tool) == SideEffectLevel.EXTERNAL_WRITE
        assert classify_risk_level(tool) == RiskLevel.CRITICAL

    def test_delete_file_destructive_critical(self):
        """delete_file → DESTRUCTIVE, CRITICAL."""
        tool = ToolArtifact(
            name="delete_file",
            description="Delete a file from the filesystem.",
            source_path="tools/fs.py",
        )
        assert classify_risk(tool) == SideEffectLevel.DESTRUCTIVE
        assert classify_risk_level(tool) == RiskLevel.CRITICAL

    def test_search_contacts_none_low(self):
        """search_contacts → NONE, LOW."""
        tool = ToolArtifact(
            name="search_contacts",
            description="Search the contact database.",
            source_path="tools/crm.py",
        )
        assert classify_risk(tool) == SideEffectLevel.NONE
        assert classify_risk_level(tool) == RiskLevel.LOW

    def test_create_draft_weak_medium(self):
        """create_draft → WEAK, MEDIUM."""
        tool = ToolArtifact(
            name="create_draft",
            description="Create a draft message.",
            source_path="tools/email.py",
        )
        assert classify_risk(tool) == SideEffectLevel.WEAK
        assert classify_risk_level(tool) == RiskLevel.MEDIUM

    def test_classify_tools_updates_in_place(self):
        """classify_tools updates side_effect_level on each tool and returns the list."""
        tools = [
            ToolArtifact(
                name="send_email",
                description="Send an email.",
                source_path="tools/email.py",
            ),
            ToolArtifact(
                name="search_contacts",
                description="Search contacts.",
                source_path="tools/crm.py",
            ),
        ]
        result = classify_tools(tools)

        assert result is tools  # Same list returned
        assert tools[0].side_effect_level == SideEffectLevel.EXTERNAL_WRITE
        assert tools[1].side_effect_level == SideEffectLevel.NONE

    def test_destructive_priority_over_external_write(self):
        """When both DESTRUCTIVE and EXTERNAL_WRITE keywords match, DESTRUCTIVE wins."""
        tool = ToolArtifact(
            name="delete_and_send_notification",
            description="Delete the record and send a notification email.",
            source_path="tools/admin.py",
        )
        assert classify_risk(tool) == SideEffectLevel.DESTRUCTIVE
        assert classify_risk_level(tool) == RiskLevel.CRITICAL

    def test_external_write_priority_over_weak(self):
        """When both EXTERNAL_WRITE and WEAK keywords match, EXTERNAL_WRITE wins."""
        tool = ToolArtifact(
            name="send_and_log",
            description="Send the message and log the action.",
            source_path="tools/messaging.py",
        )
        assert classify_risk(tool) == SideEffectLevel.EXTERNAL_WRITE
        assert classify_risk_level(tool) == RiskLevel.HIGH
