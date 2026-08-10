"""Barcode / QR label generation — ported from partner logic.py."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
BARCODE_DIR = STATIC_ROOT / "barcodes"


def generate_label(sku: str, format: str = "QR") -> Image.Image:
    """Return a PIL image for a 13mm-style label (QR or Code128)."""
    fmt = format.upper()
    if fmt == "QR":
        import qrcode

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=1,
        )
        qr.add_data(str(sku))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").get_image()
        return img.resize((150, 150), Image.Resampling.LANCZOS)

    if fmt in ("BARCODE", "CODE128"):
        import barcode
        from barcode.writer import ImageWriter

        code_class = barcode.get_barcode_class("code128")
        writer = ImageWriter()
        my_barcode = code_class(str(sku), writer=writer)
        fp = BytesIO()
        my_barcode.write(fp)
        fp.seek(0)
        img = Image.open(fp)
        return img.resize((300, 150), Image.Resampling.LANCZOS)

    raise ValueError("Unsupported format. Use 'QR' or 'Barcode'.")


def generate_item_barcode(
    sku: str,
    market_price: float | None = None,
    format: str = "QR",
) -> str:
    """Generate label PNG under static/barcodes/{sku}.png. Returns path or error."""
    try:
        img = generate_label(sku, format=format)
        BARCODE_DIR.mkdir(parents=True, exist_ok=True)
        file_path = BARCODE_DIR / f"{sku}.png"
        img.save(file_path)
        return str(file_path)
    except Exception as exc:
        return str(exc)


def barcode_public_url(sku: str) -> str:
    return f"/static/barcodes/{sku}.png"
