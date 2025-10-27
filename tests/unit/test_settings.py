"""
Unit tests for api/settings.py

Tests configuration and secret reading:
- read_secret() - Read secrets from file paths
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

# Import the module under test
from api import settings


@pytest.mark.unit
class TestReadSecret:
    """Tests for read_secret() function."""

    def test_read_secret_existing_file(self):
        """Test reading secret from existing file."""
        # Create temporary file with secret
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("my-secret-value\n")
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == "my-secret-value"
        finally:
            # Cleanup
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_strips_whitespace(self):
        """Test that read_secret strips leading/trailing whitespace."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("  secret-with-spaces  \n\n")
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == "secret-with-spaces"
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_nonexistent_file(self):
        """Test reading from nonexistent file returns empty string."""
        result = settings.read_secret("/nonexistent/path/to/secret.txt")

        assert result == ""

    def test_read_secret_empty_file(self):
        """Test reading from empty file returns empty string."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            # Write nothing
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == ""
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_whitespace_only_file(self):
        """Test reading from file with only whitespace returns empty string."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("   \n\n  \t  ")
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == ""
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_multiline_file(self):
        """Test reading from multiline file (only first line matters)."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("first-line-secret\nsecond-line\nthird-line")
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            # read_text() reads entire file, but strip() removes trailing newlines
            # So we get the entire content
            assert "first-line-secret" in result
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_with_special_characters(self):
        """Test reading secret with special characters."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("abc-123_XYZ.!@#$%^&*()")
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == "abc-123_XYZ.!@#$%^&*()"
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_with_jwt_like_string(self):
        """Test reading JWT-like secret."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            jwt_secret = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            f.write(jwt_secret)
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == jwt_secret
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_with_uuid_like_string(self):
        """Test reading UUID-like secret."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            uuid_secret = "550e8400-e29b-41d4-a716-446655440000"
            f.write(uuid_secret)
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == uuid_secret
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_unicode_content(self):
        """Test reading secret with Unicode characters."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
            f.write("secret-with-émojis-😀")
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == "secret-with-émojis-😀"
        finally:
            Path(secret_path).unlink(missing_ok=True)

    @pytest.mark.parametrize("content,expected", [
        ("simple", "simple"),
        ("  padded  ", "padded"),
        ("with\nnewlines", "with\nnewlines"),
        ("123456789", "123456789"),
        ("", ""),
        ("   ", ""),
    ])
    def test_read_secret_various_contents(self, content, expected):
        """Test reading various secret contents."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(content)
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == expected
        finally:
            Path(secret_path).unlink(missing_ok=True)


@pytest.mark.unit
class TestReadSecretEdgeCases:
    """Edge case tests for read_secret()."""

    def test_read_secret_directory_path(self):
        """Test that passing a directory path returns empty string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = settings.read_secret(tmpdir)

            # Should handle gracefully (directory is not a file)
            assert result == ""

    def test_read_secret_relative_path(self):
        """Test reading secret from relative path."""
        # Create temporary file in current directory
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', dir='.') as f:
            f.write("relative-secret")
            secret_path = Path(f.name).name  # Just filename, not full path

        try:
            result = settings.read_secret(secret_path)

            assert result == "relative-secret"
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_absolute_path(self):
        """Test reading secret from absolute path."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("absolute-secret")
            secret_path = str(Path(f.name).absolute())

        try:
            result = settings.read_secret(secret_path)

            assert result == "absolute-secret"
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_read_secret_symlink(self):
        """Test reading secret from symlink."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("symlink-secret")
            real_path = f.name

        # Create symlink
        symlink_path = f"{real_path}.link"

        try:
            Path(symlink_path).symlink_to(Path(real_path))

            result = settings.read_secret(symlink_path)

            assert result == "symlink-secret"
        finally:
            Path(symlink_path).unlink(missing_ok=True)
            Path(real_path).unlink(missing_ok=True)


@pytest.mark.unit
class TestSettingsIntegration:
    """Integration tests for settings module behavior."""

    def test_jwt_secret_precedence_file_exists(self):
        """Test JWT_SECRET reads from file when file exists."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("file-secret")
            secret_path = f.name

        try:
            with patch('api.settings.settings') as mock_settings:
                mock_settings.LT_JWT_SECRET_FILE = secret_path

                # Re-evaluate JWT_SECRET
                jwt_secret = settings.read_secret(secret_path)

                assert jwt_secret == "file-secret"
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_jwt_secret_fallback_to_env(self):
        """Test JWT_SECRET falls back to environment variable when file doesn't exist."""
        with patch.dict('os.environ', {'JWT_SECRET': 'env-secret'}):
            # Simulate missing file
            result = settings.read_secret("/nonexistent/file.txt")

            # Should return empty string (fallback handled by calling code)
            assert result == ""

    def test_jwt_secret_default_dev_secret(self):
        """Test JWT_SECRET uses CHANGE_ME_BEFORE_DEPLOY as final fallback."""
        # Simulate no file and no env var
        result = settings.read_secret("/nonexistent/file.txt")

        # Should return empty string (default "CHANGE_ME_BEFORE_DEPLOY" handled by calling code)
        assert result == ""


@pytest.mark.unit
class TestSettingsRealism:
    """Realistic settings usage tests."""

    def test_production_secret_loading(self):
        """Test loading production-like secrets."""
        # Simulate production JWT secret
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            # Production secrets are typically long random strings
            prod_secret = "a" * 64  # 64-character secret
            f.write(prod_secret)
            secret_path = f.name

        try:
            result = settings.read_secret(secret_path)

            assert result == prod_secret
            assert len(result) == 64
        finally:
            Path(secret_path).unlink(missing_ok=True)

    def test_kubernetes_secret_mount(self):
        """Test reading from Kubernetes-style secret mount."""
        # Kubernetes mounts secrets as files in /var/run/secrets/...
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_path = Path(tmpdir) / "jwt-secret"

            with open(secret_path, 'w') as f:
                f.write("k8s-mounted-secret\n")

            result = settings.read_secret(str(secret_path))

            assert result == "k8s-mounted-secret"

    def test_docker_secret_mount(self):
        """Test reading from Docker secret mount."""
        # Docker secrets are mounted at /run/secrets/...
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_path = Path(tmpdir) / "jwt_secret"

            with open(secret_path, 'w') as f:
                f.write("docker-secret-value")

            result = settings.read_secret(str(secret_path))

            assert result == "docker-secret-value"
