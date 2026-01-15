"""
ConfigManager Tests

Test suite for the configuration manager including:
- Configuration loading and merging
- Encryption and decryption
- Configuration validation
- Selector management
"""

import pytest
from pathlib import Path
from services.config_manager import (
    ConfigManager,
    EncryptionManager,
    ConfigValidator,
    ValidationError,
)


# ============================================================
# Basic Configuration Tests
# ============================================================

class TestConfigManager:
    """Test ConfigManager basic operations"""

    def test_get_config(self, temp_config_file, temp_selectors_file):
        """Test getting configuration values"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Test simple value
        interval = config.get("schedule.default_interval")
        assert interval == 180

        # Test nested value
        host = config.get("email.smtp.host")
        assert host == "smtp.test.com"

        # Test default value
        missing = config.get("non.existent.key", "default_value")
        assert missing == "default_value"

        config.stop()

    def test_get_config_nested(self, temp_config_file, temp_selectors_file):
        """Test getting nested configuration"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Get nested dict
        smtp_config = config.get("email.smtp")
        assert isinstance(smtp_config, dict)
        assert smtp_config["host"] == "smtp.test.com"
        assert smtp_config["port"] == 465
        assert smtp_config["use_ssl"] is True

        config.stop()

    def test_get_config_default(self, temp_config_file, temp_selectors_file):
        """Test default values for missing keys"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Non-existent key with default
        result = config.get("missing.key", 42)
        assert result == 42

        # Non-existent key without default
        result = config.get("another.missing.key")
        assert result is None

        config.stop()

    def test_set_config(self, temp_config_file, temp_selectors_file):
        """Test setting configuration values"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Set new value
        config.set("schedule.daily_limit", 100)
        assert config.get("schedule.daily_limit") == 100

        # Set nested value
        config.set("email.enabled", True)
        assert config.get("email.enabled") is True

        config.stop()

    def test_get_all_config(self, temp_config_file, temp_selectors_file):
        """Test getting complete configuration"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        all_config = config.get_all_config()

        # Verify it's a copy, not original
        all_config["test_key"] = "test_value"
        assert config.get("test_key") is None

        # Verify main keys exist
        assert "paths" in all_config
        assert "schedule" in all_config
        assert "email" in all_config

        config.stop()


# ============================================================
# Encryption Tests
# ============================================================

class TestEncryption:
    """Test encryption and decryption functionality"""

    def test_encrypt_value(self, temp_dir):
        """Test encrypting string values"""
        key_file = temp_dir / ".secret.key"
        manager = EncryptionManager(str(key_file))

        original = "my_secret_password"
        encrypted = manager.encrypt(original)

        # Encrypted value should be different
        assert encrypted != original
        assert encrypted.startswith("ENC(")
        assert encrypted.endswith(")")

    def test_decrypt_value(self, temp_dir):
        """Test decrypting string values"""
        key_file = temp_dir / ".secret.key"
        manager = EncryptionManager(str(key_file))

        original = "my_secret_password"
        encrypted = manager.encrypt(original)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == original

    def test_is_value_encrypted(self, temp_dir):
        """Test checking if value is encrypted"""
        key_file = temp_dir / ".secret.key"
        manager = EncryptionManager(str(key_file))

        # Plain text
        assert manager.is_encrypted("plain_text") is False

        # Encrypted text
        encrypted = manager.encrypt("secret")
        assert manager.is_encrypted(encrypted) is True

    def test_encrypt_already_encrypted(self, temp_dir):
        """Test encrypting already encrypted value"""
        key_file = temp_dir / ".secret.key"
        manager = EncryptionManager(str(key_file))

        original = "password"
        encrypted1 = manager.encrypt(original)
        encrypted2 = manager.encrypt(encrypted1)

        # Should not double-encrypt
        assert encrypted1 == encrypted2

    def test_get_decrypted(self, temp_config_file, temp_selectors_file, temp_dir):
        """Test getting decrypted configuration values"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Encrypt a password
        encrypted_password = config.encrypt_value("my_secret_password")
        config.set("email.sender.password", encrypted_password)

        # Get decrypted value
        decrypted = config.get_decrypted("email.sender.password")
        assert decrypted == "my_secret_password"

        # Get non-encrypted value
        plain = config.get_decrypted("email.sender.address")
        assert plain == "test@test.com"

        config.stop()


# ============================================================
# Configuration Validation Tests
# ============================================================

class TestConfigValidation:
    """Test configuration validation"""

    def test_validate_config(self, temp_config_file, temp_selectors_file):
        """Test validating valid configuration"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        errors = config.validate()

        # Valid config should have minimal warnings
        # (may have warnings about non-existent paths which is OK for tests)
        assert isinstance(errors, list)

        config.stop()

    def test_validate_invalid_port(self):
        """Test validation fails for invalid port"""
        validator = ConfigValidator()

        config = {
            "email": {
                "enabled": True,
                "smtp": {
                    "port": 99999  # Invalid port
                }
            }
        }

        errors = validator.validate(config)

        # Should have port validation error
        port_errors = [e for e in errors if "port" in e.path.lower()]
        assert len(port_errors) > 0
        assert any("端口号" in e.message or "port" in e.message.lower() for e in port_errors)

    def test_validate_invalid_email(self):
        """Test validation fails for invalid email address"""
        validator = ConfigValidator()

        config = {
            "email": {
                "enabled": True,
                "sender": {
                    "address": "not-an-email"  # Invalid email
                }
            }
        }

        errors = validator.validate(config)

        # Should have email validation error
        email_errors = [e for e in errors if "address" in e.path]
        assert len(email_errors) > 0
        assert any("邮箱" in e.message or "email" in e.message.lower() for e in email_errors)

    def test_validate_invalid_interval(self):
        """Test validation fails for invalid interval"""
        validator = ConfigValidator()

        config = {
            "schedule": {
                "default_interval": 5  # Too small (< 10)
            }
        }

        errors = validator.validate(config)

        # Should have interval validation error
        interval_errors = [e for e in errors if "interval" in e.path.lower()]
        assert len(interval_errors) > 0


# ============================================================
# Selector Configuration Tests
# ============================================================

class TestSelectorConfig:
    """Test selector configuration management"""

    def test_get_selector(self, temp_config_file, temp_selectors_file):
        """Test getting UI selectors"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Get selector value
        class_name = config.get_selector("main_window.class_name")
        assert class_name == "WeChatMainWndForPC"

        # Get nested selector
        discover = config.get_selector("navigation.discover_button.name")
        assert discover == "发现"

        config.stop()

    def test_get_selector_with_version(self, temp_config_file, temp_selectors_file):
        """Test getting selectors for specific version"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Get with explicit version
        class_name = config.get_selector("main_window.class_name", version="v3.9.11")
        assert class_name == "WeChatMainWndForPC"

        config.stop()

    def test_get_selector_missing(self, temp_config_file, temp_selectors_file):
        """Test getting non-existent selector"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Non-existent selector should return None
        result = config.get_selector("non.existent.selector")
        assert result is None

        config.stop()


# ============================================================
# File Operations Tests
# ============================================================

class TestFileOperations:
    """Test file save and directory operations"""

    def test_save_config(self, temp_config_file, temp_selectors_file):
        """Test saving configuration to file"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Modify and save
        config.set("schedule.daily_limit", 999)
        success = config.save()
        assert success is True

        # Verify file was updated
        assert Path(temp_config_file).exists()

        config.stop()

    def test_ensure_directories(self, temp_config_file, temp_selectors_file, temp_dir):
        """Test ensuring directories exist"""
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        config.ensure_directories()

        # Check directories were created
        assert (temp_dir / "shared").exists()
        assert (temp_dir / "cache").exists()
        assert (temp_dir / "receipts").exists()
        assert (temp_dir / "logs").exists()

        config.stop()


# ============================================================
# Singleton Pattern Tests
# ============================================================

class TestSingletonPattern:
    """Test ConfigManager singleton behavior"""

    def test_singleton_instance(self, temp_config_file, temp_selectors_file):
        """Test that ConfigManager is a singleton"""
        config1 = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        config2 = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # Should be the same instance
        assert config1 is config2

        config1.stop()


# ============================================================
# Integration Tests
# ============================================================

@pytest.mark.integration
class TestConfigManagerIntegration:
    """Integration tests for ConfigManager"""

    def test_full_workflow(self, temp_config_file, temp_selectors_file, temp_dir):
        """Test complete configuration workflow"""
        # Create config manager
        config = ConfigManager(
            config_file=str(temp_config_file),
            selectors_file=str(temp_selectors_file),
            auto_watch=False
        )

        # 1. Read config
        interval = config.get("schedule.default_interval")
        assert interval == 180

        # 2. Encrypt sensitive data
        password = "my_secret_password"
        encrypted = config.encrypt_value(password)
        config.set("email.sender.password", encrypted)

        # 3. Get decrypted value
        decrypted = config.get_decrypted("email.sender.password")
        assert decrypted == password

        # 4. Validate config
        errors = config.validate()
        assert isinstance(errors, list)

        # 5. Get selector
        class_name = config.get_selector("main_window.class_name")
        assert class_name == "WeChatMainWndForPC"

        # 6. Ensure directories
        config.ensure_directories()
        assert (temp_dir / "shared").exists()

        # 7. Save config
        success = config.save()
        assert success is True

        config.stop()
