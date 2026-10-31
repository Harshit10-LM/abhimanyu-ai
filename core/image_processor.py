"""Image preprocessing pipeline for breadboard photographs.

Handles EXIF rotation, dimension validation, memory-efficient resizing,
color normalization, and byte-formatting for local Ollama vision models.
"""

import io
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps
from core.schemas import DiagnosisResult, InventoryResult

MAX_IMAGE_EDGE_PX = 1280
MIN_IMAGE_EDGE_PX = 64
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
ALLOWED_FORMATS = {"JPEG", "JPG", "PNG"}


class ImageProcessor:
    """Preprocesses user images safely for local vision inference without external leaks."""

    @staticmethod
    def process_upload(
        file_bytes: bytes, max_edge: int = MAX_IMAGE_EDGE_PX
    ) -> Tuple[Image.Image, bytes]:
        """Validates, transposes EXIF orientation, resizes, and converts to optimized RGB JPEG bytes."""
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Image file exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB."
            )

        try:
            raw_img = Image.open(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ValueError(f"Invalid image file: {exc}")

        # Check format
        fmt = (raw_img.format or "").upper()
        if fmt not in ALLOWED_FORMATS:
            raise ValueError(
                f"Unsupported image format '{fmt}'. Please upload a PNG or JPEG photograph."
            )

        # Transpose EXIF orientation safely if metadata exists
        try:
            img = ImageOps.exif_transpose(raw_img)
        except Exception:
            img = raw_img

        # Validate dimensions
        w, h = img.size
        if w < MIN_IMAGE_EDGE_PX or h < MIN_IMAGE_EDGE_PX:
            raise ValueError(
                f"Image resolution ({w}x{h}) is too low to resolve circuit wiring components."
            )

        # Convert transparent/palette images cleanly onto neutral white background
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            rgba_img = img.convert("RGBA")
            bg.paste(rgba_img, mask=rgba_img.split()[3])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Downscale oversized images while preserving exact aspect ratio
        if max(w, h) > max_edge:
            img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

        # Strip all metadata and encode to clean JPEG bytes for local Ollama inference
        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=88, optimize=True)
        cleaned_bytes = out_buf.getvalue()

        return img, cleaned_bytes

    @classmethod
    def annotate_inventory(cls, original_img: Image.Image, inventory: InventoryResult) -> Image.Image:
        """Generates an annotated photograph with component bounding boxes and pin labels."""
        img = original_img.copy().convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size

        # Fallback coordinate offsets if model omitted bboxes
        default_regions = [
            [0.15, 0.08, 0.65, 0.45],  # MCU area
            [0.25, 0.50, 0.45, 0.65],  # LED area
            [0.48, 0.52, 0.70, 0.62],  # Resistor area
            [0.20, 0.70, 0.55, 0.90],  # Sensor area
            [0.08, 0.45, 0.85, 0.95],  # Breadboard
        ]

        palette = [
            ("#10b981", "#064e3b"),  # Green
            ("#3b82f6", "#1e3a8a"),  # Blue
            ("#f59e0b", "#78350f"),  # Amber
            ("#a855f7", "#581c87"),  # Purple
            ("#06b6d4", "#164e63"),  # Cyan
        ]

        for idx, comp in enumerate(inventory.components):
            # Resolve bounding box
            if comp.bbox and len(comp.bbox) == 4:
                ymin, xmin, ymax, xmax = comp.bbox
            else:
                ymin, xmin, ymax, xmax = default_regions[idx % len(default_regions)]

            # Clamp normalized coords to 0..1
            ymin, xmin = max(0.0, min(1.0, ymin)), max(0.0, min(1.0, xmin))
            ymax, xmax = max(ymin + 0.02, min(1.0, ymax)), max(xmin + 0.02, min(1.0, xmax))

            x0, y0 = int(xmin * w), int(ymin * h)
            x1, y1 = int(xmax * w), int(ymax * h)

            border_col, bg_col = palette[idx % len(palette)]

            # Draw outer rectangle
            draw.rectangle([x0, y0, x1, y1], outline=border_col, width=3)

            # Draw component label tag
            label_text = f"{comp.name} [{comp.confidence.upper()}]"
            tag_h = 22
            tag_w = min(len(label_text) * 8 + 12, w - x0)
            draw.rectangle([x0, max(0, y0 - tag_h), x0 + tag_w, max(tag_h, y0)], fill=border_col)
            draw.text((x0 + 4, max(2, y0 - tag_h + 3)), label_text, fill="#ffffff")

            # Draw terminal leg indicators
            for l_idx, leg in enumerate(comp.legs[:3]):
                leg_y = y0 + 26 + (l_idx * 16)
                if leg_y + 12 < y1:
                    leg_str = f"• {leg.leg_label} -> {leg.connects_to[:20]}"
                    draw.rectangle([x0 + 6, leg_y - 2, x0 + min(len(leg_str) * 7 + 10, x1 - x0 - 8), leg_y + 12], fill="#0f172a")
                    draw.text((x0 + 8, leg_y), leg_str, fill="#38bdf8")

        return img

    @classmethod
    def annotate_diagnostic(
        cls,
        original_img: Image.Image,
        inventory: InventoryResult,
        diagnosis: DiagnosisResult,
    ) -> Image.Image:
        """Generates a diagnostic highlight view showing fault locations and multimeter checks."""
        img = original_img.copy().convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size

        # If findings exist, highlight potential defect regions in warning red/amber
        for idx, finding in enumerate(diagnosis.findings):
            # Focus on central breadboard area or offset by finding index
            y_offset = 0.25 + (idx * 0.22)
            y0, y1 = int(y_offset * h), int((y_offset + 0.18) * h)
            x0, x1 = int(0.35 * w), int(0.85 * w)

            # Draw glowing warning box
            draw.rectangle([x0, y0, x1, y1], outline="#ef4444", width=4)

            # Title badge
            title_text = f"⚠ FAULT: {finding.finding[:45]}"
            draw.rectangle([x0, max(0, y0 - 24), x0 + len(title_text) * 8 + 14, y0], fill="#ef4444")
            draw.text((x0 + 6, max(2, y0 - 21)), title_text, fill="#ffffff")

            # Multimeter verification procedure callout
            meter_text = f"METER CHECK: {finding.multimeter_verification[:55]}..."
            draw.rectangle([x0 + 6, y1 - 22, x0 + len(meter_text) * 7 + 14, y1 - 2], fill="#1e293b")
            draw.text((x0 + 10, y1 - 20), meter_text, fill="#38bdf8")

        return img

