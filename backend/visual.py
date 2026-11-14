from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_PIXELS = 25_000_000
MAX_ANALYSIS_EDGE = 1000
MAX_VISUAL_ITEMS = 20
RASTER_SUFFIXES = {"png", "jpg", "jpeg", "webp"}

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def decode_image(content, expected_format=None):
    try:
        with Image.open(BytesIO(content)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Only PNG, JPEG, and WebP images are supported.")
            if expected_format and source.format != expected_format:
                raise ValueError("The image content does not match its file type.")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("This image exceeds the 25 megapixel processing limit.")
            oriented = ImageOps.exif_transpose(source)
            if "A" in oriented.getbands():
                image = Image.alpha_composite(
                    Image.new("RGBA", oriented.size, "white"),
                    oriented.convert("RGBA"),
                ).convert("RGB")
            else:
                image = oriented.convert("RGB")
            image.load()
            image.thumbnail((MAX_ANALYSIS_EDGE, MAX_ANALYSIS_EDGE), Image.Resampling.LANCZOS)
            return image
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("This image could not be decoded. Upload a valid PNG, JPEG, or WebP image.") from exc


def extract_visual_images(filename, content):
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix in RASTER_SUFFIXES:
        expected_format = "JPEG" if suffix in {"jpg", "jpeg"} else suffix.upper()
        return [(decode_image(content, expected_format), "Uploaded image")], False
    if suffix == "pdf":
        try:
            document = pymupdf.open(stream=content, filetype="pdf")
            with document:
                if len(document) > 250:
                    raise ValueError("PDFs must contain 250 pages or fewer.")
                pages_to_check = min(len(document), MAX_VISUAL_ITEMS)
                images = []
                for index in range(pages_to_check):
                    page = document[index]
                    scale = min(1.5, MAX_ANALYSIS_EDGE / max(page.rect.width, page.rect.height))
                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(scale, scale),
                        colorspace=pymupdf.csRGB,
                        alpha=False,
                    )
                    images.append(
                        (
                            Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples),
                            f"PDF page {index + 1}",
                        )
                    )
                return images, len(document) > pages_to_check
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("This PDF could not be rendered for visual review.") from exc
    if suffix == "docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                media = [
                    item for item in archive.infolist()
                    if item.filename.startswith("word/media/")
                    and PurePosixPath(item.filename).suffix.lstrip(".").lower() in RASTER_SUFFIXES
                ]
                images = []
                for item in media[:MAX_VISUAL_ITEMS]:
                    images.append((decode_image(archive.read(item)), PurePosixPath(item.filename).name))
                return images, len(media) > len(images)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Embedded images in this DOCX could not be read.") from exc
    return [], False


def _display_rgb(image):
    image = image.convert("RGB")
    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
    return image


def _dominant_colors(image):
    sample = image.copy()
    sample.thumbnail((128, 128), Image.Resampling.LANCZOS)
    quantized = sample.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert("RGB")
    total = sample.width * sample.height
    return sorted(
        ((count / total, color) for count, color in quantized.getcolors(total)),
        reverse=True,
    )


def _is_neutral(color):
    red, green, blue = color
    return max(color) - min(color) < 24 or min(color) > 242 or max(color) < 24


def _distance(first, second):
    return sum((left - right) ** 2 for left, right in zip(first, second)) ** 0.5


def _difference_hash(image):
    pixels = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS).get_flattened_data()
    value = 0
    for row in range(8):
        for column in range(8):
            value = (value << 1) | (pixels[row * 9 + column] > pixels[row * 9 + column + 1])
    return value


def _logo_matches(image, logo_bytes):
    reference = decode_image(logo_bytes)
    if min(reference.size) < 8:
        raise ValueError("Logo reference must be at least 8 pixels wide and tall.")
    reference.thumbnail((256, 256), Image.Resampling.LANCZOS)
    signature = _difference_hash(reference)
    target = _display_rgb(image)
    target_width, target_height = target.size
    aspect = reference.width / reference.height
    for fraction in (0.08, 0.14, 0.24, 0.38, 0.52):
        width = max(8, int(target_width * fraction))
        height = max(8, int(width / aspect))
        if height > target_height * 0.65:
            height = max(8, int(target_height * fraction))
            width = max(8, int(height * aspect))
        if width > target_width or height > target_height:
            continue
        step = max(3, min(width, height) // 6)
        for top in range(0, target_height - height + 1, step):
            for left in range(0, target_width - width + 1, step):
                candidate = target.crop((left, top, left + width, top + height))
                if (signature ^ _difference_hash(candidate)).bit_count() <= 5:
                    return True
    return False


def analyze_visual_image(image, palette, logo_reference=None):
    findings = []
    ranked = _dominant_colors(image)
    if palette:
        approved = [tuple(int(color[offset:offset + 2], 16) for offset in (1, 3, 5)) for color in palette]
        off_palette = [
            (share, color)
            for share, color in ranked
            if share >= 0.12 and not _is_neutral(color)
            and min(_distance(color, approved_color) for approved_color in approved) > 70
        ]
        if off_palette:
            color, share = off_palette[0][1], off_palette[0][0]
            findings.append({
                "category": "visual_color",
                "title": "Possible off-palette dominant color",
                "severity": "suggestion",
                "matched_text": f"#{color[0]:02X}{color[1]:02X}{color[2]:02X} (~{share:.0%} of sampled pixels)",
                "explanation": "A prominent color in this visual is not close to a saved brand color. Photographs and product imagery may naturally contain other colors; confirm whether it is part of the design.",
                "evidence": f"Dominant sampled color #{color[0]:02X}{color[1]:02X}{color[2]:02X}.",
                "guideline": f"Approved palette: {', '.join(palette)}",
                "suggestion": "",
            })
    else:
        findings.append({
            "category": "visual_guidance",
            "title": "Brand palette not configured",
            "severity": "info",
            "matched_text": "",
            "explanation": "Color compliance could not be compared because no approved brand colors are saved.",
            "evidence": "",
            "guideline": "Add approved hex colors in Brand guidelines to enable palette checks.",
            "suggestion": "",
        })

    if logo_reference:
        if _logo_matches(image, logo_reference):
            findings.append({
                "category": "visual_logo",
                "title": "Reference logo likely present",
                "severity": "info",
                "matched_text": "",
                "explanation": "A visual pattern similar to the saved logo reference was found. This approximate check does not verify placement, clear space, or distortion.",
                "evidence": "A shape-based comparison found a likely match.",
                "guideline": "Compare the uploaded visual with the saved logo reference.",
                "suggestion": "",
            })
        else:
            findings.append({
                "category": "visual_logo",
                "title": "Reference logo not detected",
                "severity": "suggestion",
                "matched_text": "",
                "explanation": "The saved logo reference was not confidently found. The logo may be absent, altered, or too small; some assets may not require a logo.",
                "evidence": "No sufficiently similar logo pattern was detected.",
                "guideline": "Compare the visual with the saved logo reference and intended placement.",
                "suggestion": "",
            })
    else:
        findings.append({
            "category": "visual_guidance",
            "title": "Logo reference not configured",
            "severity": "info",
            "matched_text": "",
            "explanation": "Logo usage could not be checked because no reference logo is saved.",
            "evidence": "",
            "guideline": "Add a PNG, JPEG, or WebP logo reference in Brand guidelines.",
            "suggestion": "",
        })
    return findings
