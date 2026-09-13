import io
import base64

import pyotp
import qrcode


def generate_secret():
    """Generate a new TOTP secret key."""
    return pyotp.random_base32()


def get_totp_uri(secret, username, issuer="MountainRoutes"):
    """Generate a TOTP URI for QR code (compatible with Google Authenticator)."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def generate_qr_code_base64(secret, username, issuer="MountainRoutes"):
    """Generate QR code image as base64 string."""
    uri = get_totp_uri(secret, username, issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def verify_code(secret, code):
    """Verify a TOTP code. Returns True if valid."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
