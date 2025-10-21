"""
QR code generation for room invites.

Generates QR codes that encode the invite URL.
Returns base64-encoded PNG images that can be embedded in HTML/JSON.
"""

import qrcode
import io
import base64
from typing import Optional


def generate_qr_code(invite_url: str, size: int = 300) -> str:
    """
    Generate a QR code for an invite URL.

    Args:
        invite_url: The full URL to encode (e.g., "https://example.com/join/ABC123")
        size: Size of the QR code in pixels (default: 300x300)

    Returns:
        Base64-encoded PNG image (data URL format)

    Example:
        >>> qr = generate_qr_code("https://example.com/join/ABC123")
        >>> "data:image/png;base64,iVBORw0KGgoAAAANS..."
    """
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,  # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    # Add data
    qr.add_data(invite_url)
    qr.make(fit=True)

    # Create image
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_bytes = buffer.getvalue()
    img_base64 = base64.b64encode(img_bytes).decode('utf-8')

    # Return as data URL
    return f"data:image/png;base64,{img_base64}"


def generate_qr_code_svg(invite_url: str) -> str:
    """
    Generate a QR code as SVG (scalable vector graphics).

    Args:
        invite_url: The full URL to encode

    Returns:
        SVG markup as string

    Example:
        >>> svg = generate_qr_code_svg("https://example.com/join/ABC123")
        >>> "<svg ..."
    """
    import qrcode.image.svg

    # Create QR code instance with SVG factory
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        image_factory=factory
    )

    qr.add_data(invite_url)
    qr.make(fit=True)

    # Create SVG image
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to string
    buffer = io.BytesIO()
    img.save(buffer)
    svg_bytes = buffer.getvalue()

    return svg_bytes.decode('utf-8')
