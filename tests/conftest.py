"""pytest configuration and common fixtures"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, date, timedelta

# Import project modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.task import Task
from models.content import Content
from models.stats import DailyStats, WeeklyStats, TaskSummary
from models.enums import TaskStatus, Channel, RiskLevel, CircuitState, SendStatus
from data.database import Database, reset_database


@pytest.fixture
def temp_dir():
    """Temporary directory fixture"""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
def temp_db(temp_dir):
    """Temporary database fixture"""
    db_path = temp_dir / "test.db"
    db = Database(db_path)
    yield db
    db.close()


@pytest.fixture
def sample_task():
    """Sample task fixture"""
    return Task(
        content_code="TEST001",
        product_name="Test Product",
        channel=Channel.moment,
        status=TaskStatus.pending,
        scheduled_time=datetime.now() + timedelta(hours=1),
        priority=5,
    )


@pytest.fixture
def sample_content():
    """Sample content fixture"""
    return Content(
        content_code="CONTENT001",
        text="This is test content",
        image_paths=["path/to/image1.jpg", "path/to/image2.jpg"],
        channel=Channel.moment,
    )


@pytest.fixture
def sample_daily_stats():
    """Sample daily stats fixture"""
    return DailyStats(
        stat_date=date.today(),
        total_tasks=100,
        success_count=80,
        failed_count=10,
        pending_count=10,
    )


# ============================================================
# Configuration fixtures
# ============================================================

@pytest.fixture
def temp_config_file(temp_dir):
    """Temporary config file fixture"""
    config_content = f"""
paths:
  shared_folder: {temp_dir}/shared
  cache_dir: {temp_dir}/cache
  receipts_dir: {temp_dir}/receipts
  logs_dir: {temp_dir}/logs

schedule:
  default_interval: 180
  daily_limit: 50
  active_hours:
    start: "08:00"
    end: "22:00"

email:
  enabled: false
  smtp:
    host: smtp.test.com
    port: 465
    use_ssl: true
  sender:
    address: test@test.com
    password: test_password
  recipients:
    - recipient@test.com

circuit_breaker:
  enabled: true
  failure_threshold: 3
  recovery_timeout: 300
"""
    config_file = temp_dir / "config.yaml"
    config_file.write_text(config_content, encoding="utf-8")
    return config_file


@pytest.fixture
def temp_selectors_file(temp_dir):
    """Temporary selectors file fixture"""
    selectors_content = """
default_version: v3.9.11
v3.9.11:
  main_window:
    class_name: WeChatMainWndForPC
  navigation:
    discover_button:
      name: 发现
"""
    selectors_file = temp_dir / "selectors.yaml"
    selectors_file.write_text(selectors_content, encoding="utf-8")
    return selectors_file


# ============================================================
# Mock fixtures
# ============================================================

@pytest.fixture
def mock_smtp(monkeypatch):
    """Mock SMTP server fixture"""
    from unittest.mock import Mock, MagicMock
    import smtplib

    smtp_mock = MagicMock()
    smtp_mock.sendmail = Mock(return_value={})
    smtp_mock.quit = Mock()
    smtp_mock.login = Mock()

    def mock_smtp_ssl(*args, **kwargs):
        return smtp_mock

    def mock_smtp_factory(*args, **kwargs):
        return smtp_mock

    monkeypatch.setattr(smtplib, "SMTP_SSL", mock_smtp_ssl)
    monkeypatch.setattr(smtplib, "SMTP", mock_smtp_factory)

    return smtp_mock


@pytest.fixture
def mock_clipboard(monkeypatch):
    """Mock clipboard operations"""
    from unittest.mock import Mock
    import sys

    clipboard_data = {"text": None, "opened": False}

    def mock_open():
        clipboard_data["opened"] = True

    def mock_close():
        clipboard_data["opened"] = False

    def mock_set_data(format_type, data):
        clipboard_data["text"] = data

    def mock_get_data(format_type):
        return clipboard_data.get("text", "")

    def mock_empty():
        clipboard_data["text"] = None

    def mock_is_format_available(format_type):
        return clipboard_data.get("text") is not None

    def mock_enum_formats(fmt):
        return 0

    mock_module = Mock()
    mock_module.OpenClipboard = mock_open
    mock_module.CloseClipboard = mock_close
    mock_module.SetClipboardData = mock_set_data
    mock_module.GetClipboardData = mock_get_data
    mock_module.EmptyClipboard = mock_empty
    mock_module.IsClipboardFormatAvailable = mock_is_format_available
    mock_module.EnumClipboardFormats = mock_enum_formats

    sys.modules['win32clipboard'] = mock_module
    sys.modules['win32con'] = Mock(CF_UNICODETEXT=13, CF_DIB=8)

    yield clipboard_data

    if 'win32clipboard' in sys.modules:
        del sys.modules['win32clipboard']
    if 'win32con' in sys.modules:
        del sys.modules['win32con']


# ============================================================
# Factory fixtures
# ============================================================

@pytest.fixture
def task_factory():
    """Task factory fixture"""
    def _create_task(**kwargs):
        defaults = {
            "content_code": "TEST001",
            "product_name": "Test Product",
            "channel": Channel.moment,
            "status": TaskStatus.pending,
            "scheduled_time": datetime.now(),
            "priority": 0,
        }
        defaults.update(kwargs)
        return Task(**defaults)
    return _create_task


# ============================================================
# Pytest configuration
# ============================================================

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "e2e: End-to-end tests requiring real WeChat")
    config.addinivalue_line("markers", "requires_wechat: Tests requiring WeChat client")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
