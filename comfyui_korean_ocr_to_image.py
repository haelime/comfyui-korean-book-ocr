"""ComfyUI nodes: Korean OCR and Unicode text-to-image rendering.

Copy this file to ComfyUI/custom_nodes and restart ComfyUI.
Install the optional OCR dependencies into ComfyUI's Python environment:
    python -m pip install paddlepaddle paddleocr
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
import torch
from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


def _tensor_to_rgb(image: torch.Tensor) -> np.ndarray:
    if image.ndim != 4 or image.shape[-1] < 3:
        raise ValueError("IMAGE must have shape [batch, height, width, channels].")
    return (image[0, :, :, :3].detach().cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)


def _masked_crop(rgb: np.ndarray, mask: torch.Tensor, invert: bool, margin: int):
    """Keep the painted mask region, whiten everything else, then crop to its bounds."""
    data = mask[0] if mask.ndim == 3 else mask
    data = data.detach().cpu().numpy().astype(np.float32)
    mask_image = Image.fromarray((data.clip(0, 1) * 255).astype(np.uint8))
    mask_image = mask_image.resize((rgb.shape[1], rgb.shape[0]), Image.Resampling.BILINEAR)
    alpha = np.asarray(mask_image).astype(np.float32) / 255.0
    if invert:
        alpha = 1.0 - alpha
    selected = alpha > 0.05
    if not selected.any():
        raise ValueError("마스크가 비어 있습니다. Mask Editor에서 OCR할 문단을 흰색으로 칠하세요.")
    ys, xs = np.where(selected)
    left = max(0, int(xs.min()) - margin)
    top = max(0, int(ys.min()) - margin)
    right = min(rgb.shape[1], int(xs.max()) + margin + 1)
    bottom = min(rgb.shape[0], int(ys.max()) + margin + 1)
    crop = rgb[top:bottom, left:right]
    crop_alpha = alpha[top:bottom, left:right, None]
    composed = crop * crop_alpha + 255.0 * (1.0 - crop_alpha)
    return composed.clip(0, 255).astype(np.uint8)


def _collect_text(value):
    """Extract recognized strings from PaddleOCR 2.x and 3.x result shapes."""
    found = []

    if value is None:
        return found
    if isinstance(value, str):
        return [value] if value.strip() else []
    if hasattr(value, "json"):
        try:
            payload = value.json
            payload = payload() if callable(payload) else payload
            return _collect_text(payload)
        except Exception:
            pass
    if isinstance(value, dict):
        for key in ("rec_texts", "texts"):
            if key in value:
                return _collect_text(value[key])
        for key in ("res", "result", "data"):
            if key in value:
                found.extend(_collect_text(value[key]))
        return found
    if isinstance(value, (list, tuple)):
        # PaddleOCR 2.x line: [box, (text, confidence)]
        if (
            len(value) == 2
            and isinstance(value[1], (list, tuple))
            and value[1]
            and isinstance(value[1][0], str)
        ):
            return [value[1][0]]
        for item in value:
            found.extend(_collect_text(item))
    return found


@lru_cache(maxsize=6)
def _make_ocr(version: str, angle: bool, document_unwarp: bool):
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "PaddleOCR가 없습니다. ComfyUI의 Python으로 "
            "`python -m pip install paddlepaddle paddleocr`를 실행하세요."
        ) from exc

    # Paddle 3.3.x on Windows/CPU can crash in the PIR -> oneDNN converter for
    # PP-OCRv5. The standard CPU kernels are slower but reliable.
    common = {"lang": "korean", "ocr_version": version, "enable_mkldnn": False}
    # PaddleOCR 3.x first, then the 2.x-compatible constructor.
    try:
        return PaddleOCR(
            **common,
            use_doc_orientation_classify=False,
            use_doc_unwarping=document_unwarp,
            use_textline_orientation=angle,
        )
    except TypeError:
        try:
            return PaddleOCR(**common, use_angle_cls=angle)
        except TypeError:
            return PaddleOCR(lang="korean", use_angle_cls=angle)


class KoreanOCR:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "ocr_version": (["PP-OCRv5", "PP-OCRv4", "PP-OCRv3"], {"default": "PP-OCRv5"}),
                "detect_rotation": ("BOOLEAN", {"default": True}),
                "document_unwarp": ("BOOLEAN", {"default": True}),
                "enhance_book_photo": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("korean_text",)
    FUNCTION = "recognize"
    CATEGORY = "Korean OCR"

    def recognize(self, image, ocr_version, detect_rotation, document_unwarp, enhance_book_photo):
        rgb = _tensor_to_rgb(image)
        if enhance_book_photo:
            page = Image.fromarray(rgb)
            # Book photos often have dim gutters, soft focus, and too few pixels per glyph.
            gray = ImageOps.grayscale(page)
            gray = ImageOps.autocontrast(gray, cutoff=1)
            gray = ImageEnhance.Contrast(gray).enhance(1.15)
            gray = gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=125, threshold=3))
            if min(gray.size) < 1400:
                scale = min(2.0, 1400.0 / min(gray.size))
                gray = gray.resize(
                    (round(gray.width * scale), round(gray.height * scale)),
                    Image.Resampling.LANCZOS,
                )
            rgb = np.asarray(gray.convert("RGB"))

        ocr = _make_ocr(ocr_version, detect_rotation, document_unwarp)

        try:
            result = list(ocr.predict(input=rgb))
        except (AttributeError, TypeError):
            try:
                result = ocr.ocr(rgb, cls=detect_rotation)
            except TypeError:
                result = ocr.ocr(rgb)

        lines = _collect_text(result)
        # Preserve reading order while suppressing accidental adjacent duplicates.
        cleaned = []
        for line in (str(x).strip() for x in lines):
            if line and (not cleaned or cleaned[-1] != line):
                cleaned.append(line)
        return ("\n".join(cleaned),)


class KoreanMaskedOCR(KoreanOCR):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
                "ocr_version": (["PP-OCRv5", "PP-OCRv4", "PP-OCRv3"], {"default": "PP-OCRv5"}),
                "detect_rotation": ("BOOLEAN", {"default": True}),
                "document_unwarp": ("BOOLEAN", {"default": False}),
                "enhance_book_photo": ("BOOLEAN", {"default": True}),
                "invert_mask": ("BOOLEAN", {"default": False}),
                "crop_margin": ("INT", {"default": 16, "min": 0, "max": 512}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("korean_text", "masked_preview")
    FUNCTION = "recognize_masked"
    CATEGORY = "Korean OCR"

    def recognize_masked(self, image, mask, ocr_version, detect_rotation, document_unwarp,
                         enhance_book_photo, invert_mask, crop_margin):
        cropped = _masked_crop(_tensor_to_rgb(image), mask, invert_mask, crop_margin)
        tensor = torch.from_numpy(cropped.astype(np.float32) / 255.0).unsqueeze(0)
        text = self.recognize(
            tensor, ocr_version, detect_rotation, document_unwarp, enhance_book_photo
        )[0]
        return (text, tensor)


class KoreanEditableText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ocr_text": ("STRING", {"forceInput": True}),
                "edited_text": (
                    "STRING",
                    {"default": "", "multiline": True, "dynamicPrompts": False},
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("final_text",)
    FUNCTION = "choose_text"
    CATEGORY = "Korean OCR"

    def choose_text(self, ocr_text, edited_text):
        effective = edited_text if edited_text.strip() else ocr_text
        # The frontend uses ocr_text to populate the editable widget after pass one.
        return {"ui": {"ocr_text": [ocr_text]}, "result": (effective,)}


def _font_candidates(font_path: str):
    if font_path and font_path.upper() != "AUTO":
        yield os.path.expandvars(os.path.expanduser(font_path))
    windir = os.environ.get("WINDIR", r"C:\Windows")
    yield os.path.join(windir, "Fonts", "malgun.ttf")
    yield os.path.join(windir, "Fonts", "malgunbd.ttf")
    yield "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    yield "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
    yield "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def _handwriting_font_candidates(font_path: str):
    if font_path and font_path.upper() != "AUTO":
        yield os.path.expandvars(os.path.expanduser(font_path))
    windir = os.environ.get("WINDIR", r"C:\Windows")
    # Common Windows Korean handwriting-style fonts, followed by safe fallbacks.
    yield os.path.join(windir, "Fonts", "HMFMPYUN.TTF")
    yield os.path.join(windir, "Fonts", "HMFMMUEX.TTC")
    yield os.path.join(windir, "Fonts", "H2PORL.TTF")
    yield from _font_candidates("AUTO")


def _load_font(font_path: str, size: int):
    for candidate in _font_candidates(font_path):
        if os.path.isfile(candidate):
            return ImageFont.truetype(candidate, size), candidate
    raise RuntimeError(
        "한글 폰트를 찾지 못했습니다. font_path에 NotoSansKR/NanumGothic/맑은 고딕의 "
        "TTF 또는 TTC 절대 경로를 입력하세요."
    )


def _load_handwriting_font(font_path: str, size: int):
    for candidate in _handwriting_font_candidates(font_path):
        if os.path.isfile(candidate):
            return ImageFont.truetype(candidate, size), candidate
    return _load_font("AUTO", size)


def _wrap_line(draw, line, font, max_width):
    if not line:
        return [""]
    output, current = [], ""
    for char in line:
        trial = current + char
        if current and draw.textbbox((0, 0), trial, font=font)[2] > max_width:
            output.append(current.rstrip())
            current = char.lstrip() if char.isspace() else char
        else:
            current = trial
    output.append(current)
    return output


class KoreanTextToImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
                "width": ("INT", {"default": 1024, "min": 128, "max": 8192, "step": 8}),
                "font_size": ("INT", {"default": 48, "min": 8, "max": 512}),
                "padding": ("INT", {"default": 64, "min": 0, "max": 1024}),
                "line_spacing": ("INT", {"default": 16, "min": 0, "max": 256}),
                "alignment": (["left", "center", "right"], {"default": "left"}),
                "font_path": ("STRING", {"default": "AUTO"}),
                "text_color": ("STRING", {"default": "#111111"}),
                "background_color": ("STRING", {"default": "#FFFFFF"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("text_image",)
    FUNCTION = "render"
    CATEGORY = "Korean OCR"

    def render(self, text, width, font_size, padding, line_spacing, alignment, font_path, text_color, background_color):
        font, _ = _load_font(font_path, font_size)
        scratch = Image.new("RGB", (width, 32), "white")
        draw = ImageDraw.Draw(scratch)
        usable_width = max(1, width - 2 * padding)
        lines = []
        for source_line in (text.splitlines() or [""]):
            lines.extend(_wrap_line(draw, source_line, font, usable_width))

        bbox = draw.textbbox((0, 0), "한글Ag", font=font)
        line_height = max(1, bbox[3] - bbox[1])
        height = max(128, 2 * padding + len(lines) * line_height + max(0, len(lines) - 1) * line_spacing)
        canvas = Image.new("RGB", (width, height), ImageColor.getrgb(background_color))
        draw = ImageDraw.Draw(canvas)
        y = padding
        fill = ImageColor.getrgb(text_color)
        for line in lines:
            line_width = draw.textbbox((0, 0), line, font=font)[2]
            x = padding
            if alignment == "center":
                x = (width - line_width) // 2
            elif alignment == "right":
                x = width - padding - line_width
            draw.text((x, y), line, font=font, fill=fill)
            y += line_height + line_spacing

        array = np.asarray(canvas).astype(np.float32) / 255.0
        return (torch.from_numpy(array).unsqueeze(0),)


class KoreanBookTextToImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
                "comment": (
                    "STRING",
                    {"default": "여기에 짧은 코멘트를 입력하세요.", "multiline": True, "dynamicPrompts": False},
                ),
                "width": ("INT", {"default": 1200, "min": 256, "max": 8192, "step": 8}),
                "font_size": ("INT", {"default": 48, "min": 8, "max": 512}),
                "comment_font_size": ("INT", {"default": 32, "min": 8, "max": 256}),
                "padding": ("INT", {"default": 80, "min": 0, "max": 1024}),
                "line_spacing": ("INT", {"default": 24, "min": 0, "max": 256}),
                "decoration": (["both", "highlighter", "colored_pencil_underline", "none"], {"default": "both"}),
                "font_path": ("STRING", {"default": "AUTO"}),
                "comment_font_path": ("STRING", {"default": "AUTO"}),
                "text_color": ("STRING", {"default": "#202020"}),
                "pencil_color": ("STRING", {"default": "#3F6FB5"}),
                "highlight_color": ("STRING", {"default": "#FFF176"}),
                "background_color": ("STRING", {"default": "#FFFDF7"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("annotated_page",)
    FUNCTION = "render_book_page"
    CATEGORY = "Korean OCR"

    def render_book_page(self, text, comment, width, font_size, comment_font_size, padding,
                         line_spacing, decoration, font_path, comment_font_path, text_color,
                         pencil_color, highlight_color, background_color):
        font, _ = _load_font(font_path, font_size)
        comment_font, _ = _load_handwriting_font(comment_font_path, comment_font_size)
        scratch = Image.new("RGB", (width, 64), "white")
        measure = ImageDraw.Draw(scratch)
        usable_width = max(1, width - 2 * padding)

        lines = []
        for source in (text.splitlines() or [""]):
            lines.extend(_wrap_line(measure, source, font, usable_width))
        comment_lines = []
        for source in comment.splitlines():
            comment_lines.extend(_wrap_line(measure, source, comment_font, usable_width - 48))

        main_box = measure.textbbox((0, 0), "한글Ag", font=font)
        main_height = max(1, main_box[3] - main_box[1])
        comment_box = measure.textbbox((0, 0), "한글Ag", font=comment_font)
        small_height = max(1, comment_box[3] - comment_box[1])
        main_total = len(lines) * main_height + max(0, len(lines) - 1) * line_spacing
        comment_gap = 42 if comment_lines else 0
        comment_total = len(comment_lines) * (small_height + 10)
        height = max(192, 2 * padding + main_total + comment_gap + comment_total)

        canvas = Image.new("RGBA", (width, height), ImageColor.getrgb(background_color) + (255,))
        draw = ImageDraw.Draw(canvas, "RGBA")
        y = padding
        text_fill = ImageColor.getrgb(text_color) + (255,)
        pencil_rgb = ImageColor.getrgb(pencil_color)
        highlight_rgb = ImageColor.getrgb(highlight_color)

        for index, line in enumerate(lines):
            line_width = measure.textbbox((0, 0), line, font=font)[2]
            x = padding
            if line and decoration in ("both", "highlighter"):
                top = y + int(main_height * 0.48)
                bottom = y + main_height + 5
                draw.rounded_rectangle(
                    (x - 7, top, x + line_width + 9, bottom),
                    radius=max(3, font_size // 7),
                    fill=highlight_rgb + (92,),
                )
            draw.text((x, y), line, font=font, fill=text_fill)
            if line and decoration in ("both", "colored_pencil_underline"):
                baseline = y + main_height + 7
                # Three deterministic, slightly uneven strokes mimic colored pencil grain.
                offsets = ((0, 0, 90), (2, 1, 65), (-1, 3, 45))
                for dx, dy, alpha in offsets:
                    points = []
                    segments = max(2, line_width // 24)
                    for step in range(segments + 1):
                        px = x + dx + (line_width * step / segments)
                        jitter = ((step * 7 + index * 3) % 5) - 2
                        points.append((px, baseline + dy + jitter * 0.35))
                    draw.line(points, fill=pencil_rgb + (alpha,), width=max(1, font_size // 25))
            y += main_height + line_spacing

        if comment_lines:
            y += comment_gap - line_spacing
            comment_fill = (190, 38, 45, 235)
            for index, line in enumerate(comment_lines):
                x = padding + 34 + (index % 2) * 7
                draw.text((x, y), line, font=comment_font, fill=comment_fill)
                y += small_height + 10

        rgb = canvas.convert("RGB")
        array = np.asarray(rgb).astype(np.float32) / 255.0
        return (torch.from_numpy(array).unsqueeze(0),)


NODE_CLASS_MAPPINGS = {
    "KoreanOCR": KoreanOCR,
    "KoreanMaskedOCR": KoreanMaskedOCR,
    "KoreanEditableText": KoreanEditableText,
    "KoreanTextToImage": KoreanTextToImage,
    "KoreanBookTextToImage": KoreanBookTextToImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KoreanOCR": "한국어 OCR (PaddleOCR)",
    "KoreanMaskedOCR": "마스크 영역 한국어 OCR",
    "KoreanEditableText": "OCR 텍스트 수정",
    "KoreanTextToImage": "한국어 텍스트 → 이미지",
    "KoreanBookTextToImage": "책 문장 꾸미기 → 이미지",
}

WEB_DIRECTORY = "./comfyui_korean_ocr_web"
