"""Tests for enum models"""
import pytest
from models.enums import TaskStatus, Channel, RiskLevel, CircuitState, SendStatus


class TestTaskStatus:
    """Test TaskStatus enum"""

    def test_all_status_values(self):
        """Test all TaskStatus values exist"""
        assert TaskStatus.pending.value == "pending"
        assert TaskStatus.scheduled.value == "scheduled"
        assert TaskStatus.running.value == "running"
        assert TaskStatus.success.value == "success"
        assert TaskStatus.failed.value == "failed"
        assert TaskStatus.skipped.value == "skipped"
        assert TaskStatus.cancelled.value == "cancelled"
        assert TaskStatus.paused.value == "paused"

    def test_status_string_inheritance(self):
        """Test that TaskStatus inherits from str"""
        assert isinstance(TaskStatus.pending, str)
        assert isinstance(TaskStatus.success, str)

    def test_status_equality(self):
        """Test TaskStatus equality comparisons"""
        assert TaskStatus.pending == "pending"
        assert TaskStatus.success == TaskStatus.success
        assert TaskStatus.pending != TaskStatus.running

    def test_status_from_string(self):
        """Test creating TaskStatus from string"""
        status = TaskStatus("pending")
        assert status == TaskStatus.pending

        status = TaskStatus("success")
        assert status == TaskStatus.success

    def test_invalid_status_raises_error(self):
        """Test that invalid status string raises ValueError"""
        with pytest.raises(ValueError):
            TaskStatus("invalid_status")


class TestChannel:
    """Test Channel enum"""

    def test_all_channel_values(self):
        """Test all Channel values exist"""
        assert Channel.moment.value == "moment"
        assert Channel.group.value == "group"

    def test_channel_string_inheritance(self):
        """Test that Channel inherits from str"""
        assert isinstance(Channel.moment, str)
        assert isinstance(Channel.group, str)

    def test_channel_equality(self):
        """Test Channel equality comparisons"""
        assert Channel.moment == "moment"
        assert Channel.group == "group"
        assert Channel.moment != Channel.group

    def test_channel_from_string(self):
        """Test creating Channel from string"""
        channel = Channel("moment")
        assert channel == Channel.moment

        channel = Channel("group")
        assert channel == Channel.group

    def test_invalid_channel_raises_error(self):
        """Test that invalid channel string raises ValueError"""
        with pytest.raises(ValueError):
            Channel("invalid_channel")


class TestRiskLevel:
    """Test RiskLevel enum"""

    def test_all_risk_level_values(self):
        """Test all RiskLevel values exist"""
        assert RiskLevel.low.value == "low"
        assert RiskLevel.medium.value == "medium"
        assert RiskLevel.high.value == "high"
        assert RiskLevel.critical.value == "critical"

    def test_risk_level_string_inheritance(self):
        """Test that RiskLevel inherits from str"""
        assert isinstance(RiskLevel.low, str)
        assert isinstance(RiskLevel.critical, str)

    def test_risk_level_equality(self):
        """Test RiskLevel equality comparisons"""
        assert RiskLevel.low == "low"
        assert RiskLevel.critical == "critical"
        assert RiskLevel.low != RiskLevel.high

    def test_risk_level_from_string(self):
        """Test creating RiskLevel from string"""
        level = RiskLevel("low")
        assert level == RiskLevel.low

        level = RiskLevel("critical")
        assert level == RiskLevel.critical

    def test_invalid_risk_level_raises_error(self):
        """Test that invalid risk level string raises ValueError"""
        with pytest.raises(ValueError):
            RiskLevel("invalid_level")


class TestCircuitState:
    """Test CircuitState enum"""

    def test_all_circuit_state_values(self):
        """Test all CircuitState values exist"""
        assert CircuitState.closed.value == "closed"
        assert CircuitState.open.value == "open"
        assert CircuitState.half_open.value == "half_open"

    def test_circuit_state_string_inheritance(self):
        """Test that CircuitState inherits from str"""
        assert isinstance(CircuitState.closed, str)
        assert isinstance(CircuitState.open, str)
        assert isinstance(CircuitState.half_open, str)

    def test_circuit_state_equality(self):
        """Test CircuitState equality comparisons"""
        assert CircuitState.closed == "closed"
        assert CircuitState.open == "open"
        assert CircuitState.half_open == "half_open"
        assert CircuitState.closed != CircuitState.open

    def test_circuit_state_from_string(self):
        """Test creating CircuitState from string"""
        state = CircuitState("closed")
        assert state == CircuitState.closed

        state = CircuitState("half_open")
        assert state == CircuitState.half_open

    def test_invalid_circuit_state_raises_error(self):
        """Test that invalid circuit state string raises ValueError"""
        with pytest.raises(ValueError):
            CircuitState("invalid_state")


class TestSendStatus:
    """Test SendStatus enum"""

    def test_all_send_status_values(self):
        """Test all SendStatus values exist"""
        assert SendStatus.SUCCESS.value == "success"
        assert SendStatus.FAILED.value == "failed"
        assert SendStatus.PARTIAL.value == "partial"
        assert SendStatus.TIMEOUT.value == "timeout"
        assert SendStatus.CANCELLED.value == "cancelled"
        assert SendStatus.GROUP_NOT_FOUND.value == "group_not_found"
        assert SendStatus.WECHAT_ERROR.value == "wechat_error"

    def test_send_status_string_inheritance(self):
        """Test that SendStatus inherits from str"""
        assert isinstance(SendStatus.SUCCESS, str)
        assert isinstance(SendStatus.FAILED, str)
        assert isinstance(SendStatus.WECHAT_ERROR, str)

    def test_send_status_equality(self):
        """Test SendStatus equality comparisons"""
        assert SendStatus.SUCCESS == "success"
        assert SendStatus.FAILED == "failed"
        assert SendStatus.GROUP_NOT_FOUND == "group_not_found"
        assert SendStatus.SUCCESS != SendStatus.FAILED

    def test_send_status_from_string(self):
        """Test creating SendStatus from string"""
        status = SendStatus("success")
        assert status == SendStatus.SUCCESS

        status = SendStatus("group_not_found")
        assert status == SendStatus.GROUP_NOT_FOUND

    def test_invalid_send_status_raises_error(self):
        """Test that invalid send status string raises ValueError"""
        with pytest.raises(ValueError):
            SendStatus("invalid_status")


class TestEnumInteroperability:
    """Test enum interoperability"""

    def test_enums_in_collections(self):
        """Test that enums work in collections"""
        statuses = {TaskStatus.pending, TaskStatus.success, TaskStatus.failed}
        assert TaskStatus.pending in statuses
        assert TaskStatus.running not in statuses

    def test_enums_as_dict_keys(self):
        """Test that enums work as dictionary keys"""
        status_map = {
            TaskStatus.pending: "Waiting",
            TaskStatus.success: "Done",
            TaskStatus.failed: "Error"
        }
        assert status_map[TaskStatus.pending] == "Waiting"
        assert status_map[TaskStatus.success] == "Done"

    def test_enums_in_conditionals(self):
        """Test that enums work in conditional statements"""
        status = TaskStatus.success

        if status == TaskStatus.success:
            result = "success"
        else:
            result = "not success"

        assert result == "success"
