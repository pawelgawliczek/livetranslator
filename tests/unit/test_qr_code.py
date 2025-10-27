"""
Unit tests for api/utils/qr_code.py

Tests QR code generation for room invites:
- generate_qr_code() - PNG QR codes as base64 data URLs
- generate_qr_code_svg() - SVG QR codes

Key features tested:
- Base64 PNG encoding
- SVG generation
- Various URL formats
- Size parameters
- Data URL format
"""

import pytest
import base64
import re

# Import the module under test
from api.utils import qr_code


@pytest.mark.unit
class TestGenerateQRCode:
    """Tests for generate_qr_code() function (PNG/base64)."""

    def test_generate_qr_code_returns_data_url(self, sample_invite_url):
        """Test that QR code is returned as data URL."""
        result = qr_code.generate_qr_code(sample_invite_url)

        assert result is not None
        assert isinstance(result, str)
        assert result.startswith("data:image/png;base64,")

    def test_generate_qr_code_contains_valid_base64(self, sample_invite_url):
        """Test that QR code contains valid base64 data."""
        result = qr_code.generate_qr_code(sample_invite_url)

        # Extract base64 part
        base64_data = result.split(",", 1)[1]

        # Should be valid base64
        try:
            decoded = base64.b64decode(base64_data)
            assert len(decoded) > 0
            # PNG files start with specific magic bytes
            assert decoded[:8] == b'\x89PNG\r\n\x1a\n'
        except Exception as e:
            pytest.fail(f"Invalid base64 or PNG data: {e}")

    def test_generate_qr_code_is_png_image(self, sample_invite_url):
        """Test that generated QR code is a valid PNG image."""
        result = qr_code.generate_qr_code(sample_invite_url)

        base64_data = result.split(",", 1)[1]
        decoded = base64.b64decode(base64_data)

        # PNG signature: 89 50 4E 47 0D 0A 1A 0A
        png_signature = b'\x89PNG\r\n\x1a\n'
        assert decoded.startswith(png_signature)

    def test_generate_qr_code_with_default_size(self, sample_invite_url):
        """Test QR generation with default size (300x300)."""
        result = qr_code.generate_qr_code(sample_invite_url)

        assert result is not None
        assert len(result) > 100  # Should have substantial data

    def test_generate_qr_code_with_custom_size(self, sample_invite_url):
        """Test QR generation with custom size."""
        result_small = qr_code.generate_qr_code(sample_invite_url, size=200)
        result_large = qr_code.generate_qr_code(sample_invite_url, size=500)

        assert result_small is not None
        assert result_large is not None

        # Both should be valid data URLs
        assert result_small.startswith("data:image/png;base64,")
        assert result_large.startswith("data:image/png;base64,")

    @pytest.mark.parametrize("url", [
        "https://example.com/join/ABC123",
        "https://livetranslator.com/join/test-room",
        "https://app.example.com/r/room-12345?invite=xyz",
        "https://localhost:9003/join/dev-room",
    ])
    def test_generate_qr_code_with_various_urls(self, url):
        """Test QR generation with various URL formats."""
        result = qr_code.generate_qr_code(url)

        assert result is not None
        assert result.startswith("data:image/png;base64,")

        # Verify it's valid base64
        base64_data = result.split(",", 1)[1]
        decoded = base64.b64decode(base64_data)
        assert decoded.startswith(b'\x89PNG\r\n\x1a\n')

    def test_generate_qr_code_different_urls_different_codes(self):
        """Test that different URLs generate different QR codes."""
        url1 = "https://example.com/join/room-1"
        url2 = "https://example.com/join/room-2"

        qr1 = qr_code.generate_qr_code(url1)
        qr2 = qr_code.generate_qr_code(url2)

        assert qr1 != qr2

    def test_generate_qr_code_same_url_same_code(self, sample_invite_url):
        """Test that same URL generates same QR code (deterministic)."""
        qr1 = qr_code.generate_qr_code(sample_invite_url)
        qr2 = qr_code.generate_qr_code(sample_invite_url)

        assert qr1 == qr2

    def test_generate_qr_code_with_long_url(self):
        """Test QR generation with very long URL."""
        long_url = "https://example.com/join/room-" + "a" * 200 + "?invite=" + "b" * 100

        result = qr_code.generate_qr_code(long_url)

        assert result is not None
        assert result.startswith("data:image/png;base64,")

    def test_generate_qr_code_with_special_characters(self):
        """Test QR generation with special characters in URL."""
        url = "https://example.com/join/room-123?invite=abc&ref=def&lang=pl-PL"

        result = qr_code.generate_qr_code(url)

        assert result is not None
        assert result.startswith("data:image/png;base64,")

    def test_generate_qr_code_base64_no_padding_issues(self, sample_invite_url):
        """Test that base64 encoding has no padding issues."""
        result = qr_code.generate_qr_code(sample_invite_url)

        base64_data = result.split(",", 1)[1]

        # Should decode without errors
        try:
            base64.b64decode(base64_data)
        except Exception as e:
            pytest.fail(f"Base64 decoding failed: {e}")

    def test_generate_qr_code_returns_non_empty(self, sample_invite_url):
        """Test that QR code data is not empty."""
        result = qr_code.generate_qr_code(sample_invite_url)

        # Extract base64 data
        base64_data = result.split(",", 1)[1]

        assert len(base64_data) > 0
        assert len(base64_data) > 100  # Should be substantial

    def test_generate_qr_code_contains_only_valid_characters(self, sample_invite_url):
        """Test that data URL contains only valid characters."""
        result = qr_code.generate_qr_code(sample_invite_url)

        # Data URL format: data:image/png;base64,<base64-data>
        assert re.match(r'^data:image/png;base64,[A-Za-z0-9+/=]+$', result)


@pytest.mark.unit
class TestGenerateQRCodeSVG:
    """Tests for generate_qr_code_svg() function."""

    def test_generate_qr_code_svg_returns_svg_string(self, sample_invite_url):
        """Test that SVG QR code is returned as string."""
        result = qr_code.generate_qr_code_svg(sample_invite_url)

        assert result is not None
        assert isinstance(result, str)
        assert "<svg" in result

    def test_generate_qr_code_svg_is_valid_svg(self, sample_invite_url):
        """Test that generated string is valid SVG markup."""
        result = qr_code.generate_qr_code_svg(sample_invite_url)

        # Check for SVG tags
        assert "<svg" in result
        assert "</svg>" in result
        assert "xmlns" in result.lower()

    def test_generate_qr_code_svg_contains_path_elements(self, sample_invite_url):
        """Test that SVG contains path elements (QR code data)."""
        result = qr_code.generate_qr_code_svg(sample_invite_url)

        # SVG QR codes typically use <path> or <rect> elements
        assert "<path" in result or "<rect" in result

    @pytest.mark.parametrize("url", [
        "https://example.com/join/ABC123",
        "https://livetranslator.com/join/test-room",
        "https://app.example.com/r/room-12345",
    ])
    def test_generate_qr_code_svg_with_various_urls(self, url):
        """Test SVG QR generation with various URLs."""
        result = qr_code.generate_qr_code_svg(url)

        assert result is not None
        assert "<svg" in result
        assert "</svg>" in result

    def test_generate_qr_code_svg_different_urls_different_codes(self):
        """Test that different URLs generate different SVG QR codes."""
        url1 = "https://example.com/join/room-1"
        url2 = "https://example.com/join/room-2"

        svg1 = qr_code.generate_qr_code_svg(url1)
        svg2 = qr_code.generate_qr_code_svg(url2)

        assert svg1 != svg2

    def test_generate_qr_code_svg_same_url_same_code(self, sample_invite_url):
        """Test that same URL generates same SVG (deterministic)."""
        svg1 = qr_code.generate_qr_code_svg(sample_invite_url)
        svg2 = qr_code.generate_qr_code_svg(sample_invite_url)

        assert svg1 == svg2

    def test_generate_qr_code_svg_is_utf8_string(self, sample_invite_url):
        """Test that SVG is valid UTF-8 string."""
        result = qr_code.generate_qr_code_svg(sample_invite_url)

        # Should be decodable as UTF-8
        assert isinstance(result, str)
        # Can encode back to UTF-8
        result.encode('utf-8')

    def test_generate_qr_code_svg_with_long_url(self):
        """Test SVG QR generation with very long URL."""
        long_url = "https://example.com/join/room-" + "a" * 200

        result = qr_code.generate_qr_code_svg(long_url)

        assert result is not None
        assert "<svg" in result

    def test_generate_qr_code_svg_with_special_characters(self):
        """Test SVG QR generation with special characters in URL."""
        url = "https://example.com/join/room-123?invite=abc&ref=def"

        result = qr_code.generate_qr_code_svg(url)

        assert result is not None
        assert "<svg" in result


@pytest.mark.unit
class TestQRCodeFormats:
    """Tests comparing PNG and SVG formats."""

    def test_png_and_svg_both_work_for_same_url(self, sample_invite_url):
        """Test that both PNG and SVG generation work for same URL."""
        png_qr = qr_code.generate_qr_code(sample_invite_url)
        svg_qr = qr_code.generate_qr_code_svg(sample_invite_url)

        assert png_qr is not None
        assert svg_qr is not None

        # Different formats
        assert png_qr.startswith("data:image/png;base64,")
        assert svg_qr.startswith("<")  # SVG starts with <

    def test_png_and_svg_are_different_formats(self, sample_invite_url):
        """Test that PNG and SVG are different representations."""
        png_qr = qr_code.generate_qr_code(sample_invite_url)
        svg_qr = qr_code.generate_qr_code_svg(sample_invite_url)

        # Should be completely different formats
        assert png_qr != svg_qr
        assert "base64" in png_qr
        assert "svg" in svg_qr


@pytest.mark.unit
class TestQRCodeEdgeCases:
    """Edge case tests for QR code generation."""

    def test_generate_qr_code_with_empty_url(self):
        """Test QR generation with empty URL (should still work)."""
        result = qr_code.generate_qr_code("")

        # QR code can encode empty string
        assert result is not None
        assert result.startswith("data:image/png;base64,")

    def test_generate_qr_code_with_unicode_url(self):
        """Test QR generation with Unicode characters in URL."""
        unicode_url = "https://example.com/join/pokój-testowy-żółć"

        result = qr_code.generate_qr_code(unicode_url)

        assert result is not None
        assert result.startswith("data:image/png;base64,")

    def test_generate_qr_code_svg_with_unicode_url(self):
        """Test SVG QR generation with Unicode characters."""
        unicode_url = "https://example.com/join/pokój-testowy"

        result = qr_code.generate_qr_code_svg(unicode_url)

        assert result is not None
        assert "<svg" in result

    def test_generate_qr_code_with_very_short_url(self):
        """Test QR generation with very short URL."""
        short_url = "https://t.co/abc"

        result = qr_code.generate_qr_code(short_url)

        assert result is not None
        assert result.startswith("data:image/png;base64,")

    def test_generate_qr_code_deterministic_generation(self, sample_invite_url):
        """Test that QR generation is deterministic (same input = same output)."""
        results = [qr_code.generate_qr_code(sample_invite_url) for _ in range(5)]

        # All should be identical
        assert all(r == results[0] for r in results)
