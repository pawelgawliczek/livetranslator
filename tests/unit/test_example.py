"""
Example unit tests demonstrating test structure and patterns.

These are fast, isolated tests with no I/O operations.
"""
import pytest


class TestExampleUnitTests:
    """Example unit test class."""

    def test_basic_assertion(self):
        """Test basic Python assertion."""
        result = 2 + 2
        assert result == 4

    def test_string_operations(self):
        """Test string manipulation."""
        text = "LiveTranslator"
        assert text.lower() == "livetranslator"
        assert len(text) == 14
        assert text.startswith("Live")

    def test_list_operations(self):
        """Test list operations."""
        languages = ["en", "pl", "ar"]
        assert "en" in languages
        assert len(languages) == 3
        assert languages[0] == "en"

    def test_dictionary_operations(self):
        """Test dictionary operations."""
        user = {
            "id": 123,
            "email": "test@example.com",
            "lang": "en"
        }
        assert user["id"] == 123
        assert user.get("email") == "test@example.com"
        assert "lang" in user

    @pytest.mark.parametrize("input_lang,expected", [
        ("en-US", "en"),
        ("pl-PL", "pl"),
        ("ar-EG", "ar"),
    ])
    def test_language_code_extraction(self, input_lang, expected):
        """Test extracting language code from locale."""
        result = input_lang.split("-")[0]
        assert result == expected


class TestExampleWithFixtures:
    """Example tests using fixtures."""

    @pytest.fixture
    def sample_user(self):
        """Fixture providing sample user data."""
        return {
            "id": 123,
            "email": "test@example.com",
            "display_name": "Test User",
            "preferred_lang": "en"
        }

    @pytest.fixture
    def sample_room(self):
        """Fixture providing sample room data."""
        return {
            "code": "test-room",
            "owner_id": 123,
            "is_public": False,
            "max_participants": 10
        }

    def test_user_fixture(self, sample_user):
        """Test using user fixture."""
        assert sample_user["id"] == 123
        assert "@" in sample_user["email"]

    def test_room_fixture(self, sample_room):
        """Test using room fixture."""
        assert sample_room["code"] == "test-room"
        assert sample_room["owner_id"] == 123


class TestExampleErrorHandling:
    """Example tests for error handling."""

    def test_exception_raised(self):
        """Test that exception is raised."""
        with pytest.raises(ValueError):
            raise ValueError("Test error")

    def test_exception_message(self):
        """Test exception message."""
        with pytest.raises(ValueError, match="invalid"):
            raise ValueError("invalid input")

    def test_zero_division(self):
        """Test zero division error."""
        with pytest.raises(ZeroDivisionError):
            result = 1 / 0


@pytest.mark.unit
class TestMarkedTests:
    """Tests with pytest markers."""

    @pytest.mark.unit
    def test_marked_as_unit(self):
        """This test is marked as a unit test."""
        assert True

    @pytest.mark.slow
    def test_slow_operation(self):
        """This test is marked as slow (skip in quick runs)."""
        # Simulate slow operation
        import time
        time.sleep(0.1)
        assert True


# Async test example (for future use)
@pytest.mark.asyncio
async def test_async_example():
    """Example async test."""
    import asyncio

    async def async_function():
        await asyncio.sleep(0.01)
        return "result"

    result = await async_function()
    assert result == "result"
