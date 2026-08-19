"""ComfyUI nodes: Korean OCR and Unicode text-to-image rendering.

Copy this file to ComfyUI/custom_nodes and restart ComfyUI.
Install the optional OCR dependencies into ComfyUI's Python environment:
    python -m pip install paddlepaddle paddleocr
"""

from __future__ import annotations

import os
import re
import json
import urllib.error
import urllib.request
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
                "이미지": ("IMAGE",),
                "OCR_버전": (["PP-OCRv5", "PP-OCRv4", "PP-OCRv3"], {"default": "PP-OCRv5"}),
                "회전_감지": ("BOOLEAN", {"default": True}),
                "문서_펴기": ("BOOLEAN", {"default": True}),
                "책_사진_보정": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("한국어_텍스트",)
    FUNCTION = "recognize"
    CATEGORY = "한국어 OCR"

    def recognize(self, 이미지, OCR_버전, 회전_감지, 문서_펴기, 책_사진_보정):
        rgb = _tensor_to_rgb(이미지)
        if 책_사진_보정:
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

        ocr = _make_ocr(OCR_버전, 회전_감지, 문서_펴기)

        try:
            result = list(ocr.predict(input=rgb))
        except (AttributeError, TypeError):
            try:
                result = ocr.ocr(rgb, cls=회전_감지)
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
                "이미지": ("IMAGE",),
                "마스크": ("MASK",),
                "OCR_버전": (["PP-OCRv5", "PP-OCRv4", "PP-OCRv3"], {"default": "PP-OCRv5"}),
                "회전_감지": ("BOOLEAN", {"default": True}),
                "문서_펴기": ("BOOLEAN", {"default": False}),
                "책_사진_보정": ("BOOLEAN", {"default": True}),
                "마스크_반전": ("BOOLEAN", {"default": False}),
                "자르기_여백": ("INT", {"default": 16, "min": 0, "max": 512}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("한국어_텍스트", "마스크_미리보기")
    FUNCTION = "recognize_masked"
    CATEGORY = "한국어 OCR"

    def recognize_masked(self, 이미지, 마스크, OCR_버전, 회전_감지, 문서_펴기,
                         책_사진_보정, 마스크_반전, 자르기_여백):
        cropped = _masked_crop(_tensor_to_rgb(이미지), 마스크, 마스크_반전, 자르기_여백)
        tensor = torch.from_numpy(cropped.astype(np.float32) / 255.0).unsqueeze(0)
        text = self.recognize(
            tensor, OCR_버전, 회전_감지, 문서_펴기, 책_사진_보정
        )[0]
        return (text, tensor)


class KoreanOCRAutoCorrect:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "OCR_텍스트": ("STRING", {"forceInput": True}),
                "자동_교정": ("BOOLEAN", {"default": True}),
                "모델": ("STRING", {"default": "qwen3:8b"}),
                "교정_강도": (["보수적", "일반"], {"default": "보수적"}),
                "고유명사_보존": ("BOOLEAN", {"default": True}),
                "꾸밈_선택": (["자동 추천 사용", "추천 없이 교정만"], {"default": "자동 추천 사용"}),
                "올라마_주소": ("STRING", {"default": "http://127.0.0.1:11434"}),
                "제한_시간_초": ("INT", {"default": 180, "min": 10, "max": 1800}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("선택_텍스트", "교정_텍스트", "꾸밈_추천_텍스트")
    FUNCTION = "교정"
    CATEGORY = "한국어 OCR"

    def 교정(self, OCR_텍스트, 자동_교정, 모델, 교정_강도, 고유명사_보존,
             꾸밈_선택, 올라마_주소, 제한_시간_초):
        if not 자동_교정 or not OCR_텍스트.strip():
            return (OCR_텍스트, OCR_텍스트, OCR_텍스트)

        strength = (
            "명백한 OCR 오인식, 띄어쓰기, 문장부호만 고치고 문체와 어휘는 바꾸지 마라."
            if 교정_강도 == "보수적"
            else "OCR 오인식과 맞춤법을 고치되 원문의 의미와 문체를 유지하라."
        )
        proper_nouns = (
            "사람 이름, 지명, 작품명 등 고유명사는 확실한 근거가 없으면 절대 바꾸지 마라."
            if 고유명사_보존 else "문맥상 명백히 잘못 인식된 고유명사는 교정해도 된다."
        )
        prompt = (
            "다음은 한국어 소설책 사진에서 추출한 OCR 텍스트다.\n"
            f"{strength}\n{proper_nouns}\n"
            "문단과 줄바꿈을 가능한 한 보존하고, 내용을 추가·요약·번역하지 마라. "
            "corrected_text에는 Markdown 없는 순수 교정문을 넣어라. "
            "recommended_markdown에는 교정문 내용은 그대로 두고 아래 꾸밈 기호만 삽입해라.\n"
            "- 핵심 문장이나 구절 1~2곳: __색연필 밑줄__\n"
            "- 내면 독백이나 약한 강조 0~1곳: *이탤릭*\n"
            "- 기억할 표현 0~2곳: ~~형광펜~~\n"
            "- 밑줄에 짧은 감상 댓글이 어울리면 __구절__[^1]과 [^1]: 댓글 형식을 사용\n"
            "과하게 꾸미지 말고, 코드 블록이나 다른 Markdown 문법은 쓰지 마라.\n"
            "출력은 corrected_text와 recommended_markdown 필드를 가진 JSON 객체여야 한다.\n\n"
            f"OCR 원문:\n{OCR_텍스트}"
        )
        schema = {
            "type": "object",
            "properties": {
                "corrected_text": {"type": "string"},
                "recommended_markdown": {"type": "string"},
            },
            "required": ["corrected_text", "recommended_markdown"],
        }
        payload = json.dumps({
            "model": 모델.strip() or "qwen3:8b",
            "prompt": prompt,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0.1},
        }, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            올라마_주소.rstrip("/") + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=제한_시간_초) as response:
                result = json.loads(response.read().decode("utf-8"))
            generated = json.loads(result.get("response", "{}"))
            corrected = generated["corrected_text"].strip() or OCR_텍스트
            recommended = generated["recommended_markdown"].strip() or corrected
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "로컬 AI(Ollama)에 연결하지 못했습니다. Ollama가 실행 중인지 확인하세요: "
                f"{올라마_주소}"
            ) from exc
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError("로컬 AI 교정 결과를 읽지 못했습니다. 다시 실행해 주세요.") from exc
        selected = recommended if 꾸밈_선택 == "자동 추천 사용" else corrected
        return (selected, corrected, recommended)


_FONT_LABELS = ["자동 (맑은 고딕)", "맑은 고딕", "맑은 고딕 굵게", "맑은 고딕 가늘게",
                "굴림", "바탕", "Noto Sans KR", "Noto Serif KR", "직접 입력"]


def _selected_font_path(label, direct_path):
    if direct_path.strip():
        return direct_path.strip()
    windir = os.environ.get("WINDIR", r"C:\Windows")
    filenames = {
        "맑은 고딕": "malgun.ttf",
        "맑은 고딕 굵게": "malgunbd.ttf",
        "맑은 고딕 가늘게": "malgunsl.ttf",
        "굴림": "gulim.ttc",
        "바탕": "batang.ttc",
        "Noto Sans KR": "NotoSansKR-VF.ttf",
        "Noto Serif KR": "NotoSerifKR-VF.ttf",
    }
    filename = filenames.get(label)
    return os.path.join(windir, "Fonts", filename) if filename else "AUTO"


class KoreanTextStyleSettings:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "이미지_너비": ("INT", {"default": 1200, "min": 256, "max": 8192, "step": 8}),
                "본문_글꼴": (_FONT_LABELS, {"default": "자동 (맑은 고딕)"}),
                "직접_글꼴_경로": ("STRING", {"default": ""}),
                "본문_크기": ("INT", {"default": 48, "min": 8, "max": 512}),
                "댓글_글꼴": (_FONT_LABELS, {"default": "맑은 고딕"}),
                "직접_댓글_글꼴_경로": ("STRING", {"default": ""}),
                "댓글_크기": ("INT", {"default": 32, "min": 8, "max": 256}),
                "여백": ("INT", {"default": 80, "min": 0, "max": 1024}),
                "줄_간격": ("INT", {"default": 24, "min": 0, "max": 256}),
                "본문_색": ("STRING", {"default": "#202020"}),
                "밑줄_색": ("STRING", {"default": "#C63B3B"}),
                "형광펜_색": ("STRING", {"default": "#FFF176"}),
                "배경_색": ("STRING", {"default": "#FFFDF7"}),
            }
        }

    RETURN_TYPES = ("KOREAN_TEXT_STYLE", "IMAGE")
    RETURN_NAMES = ("스타일_설정", "스타일_미리보기")
    FUNCTION = "설정"
    CATEGORY = "한국어 OCR"

    def 설정(self, 이미지_너비, 본문_글꼴, 직접_글꼴_경로, 본문_크기,
             댓글_글꼴, 직접_댓글_글꼴_경로, 댓글_크기, 여백, 줄_간격,
             본문_색, 밑줄_색, 형광펜_색, 배경_색):
        style = {
            "width": 이미지_너비,
            "font_size": 본문_크기,
            "comment_font_size": 댓글_크기,
            "padding": 여백,
            "line_spacing": 줄_간격,
            "font_path": _selected_font_path(본문_글꼴, 직접_글꼴_경로),
            "comment_font_path": _selected_font_path(댓글_글꼴, 직접_댓글_글꼴_경로),
            "text_color": 본문_색,
            "pencil_color": 밑줄_색,
            "highlight_color": 형광펜_색,
            "background_color": 배경_색,
        }
        sample = (
            "글꼴과 크기 미리보기\n"
            "__붉은 색연필 밑줄__[^1]  *이탤릭*  ~~형광펜~~\n\n"
            "[^1]: 작은 붉은 글씨 댓글"
        )
        image = KoreanBookTextToImage().render_book_page(
            sample, "", style["width"], style["font_size"],
            style["comment_font_size"], style["padding"], style["line_spacing"],
            style["font_path"], style["comment_font_path"], style["text_color"],
            style["pencil_color"], style["highlight_color"], style["background_color"],
        )[0]
        return (style, image)


class KoreanEditableText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "OCR_텍스트": ("STRING", {"forceInput": True}),
                "스타일_설정": ("KOREAN_TEXT_STYLE", {"forceInput": True}),
                "수정_텍스트": (
                    "STRING",
                    {"default": "", "multiline": True, "dynamicPrompts": False},
                ),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("최종_텍스트", "꾸민_이미지")
    FUNCTION = "choose_text"
    CATEGORY = "한국어 OCR"

    def choose_text(self, OCR_텍스트, 스타일_설정, 수정_텍스트):
        effective = 수정_텍스트 if 수정_텍스트.strip() else OCR_텍스트
        style = 스타일_설정
        image = KoreanBookTextToImage().render_book_page(
            effective, "", style["width"], style["font_size"],
            style["comment_font_size"], style["padding"], style["line_spacing"],
            style["font_path"], style["comment_font_path"], style["text_color"],
            style["pencil_color"], style["highlight_color"], style["background_color"],
        )[0]
        # The frontend uses source_text to populate the editable widget after pass one.
        return {"ui": {"source_text": [OCR_텍스트]}, "result": (effective, image)}


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


def _parse_inline_markdown(line: str):
    """Parse the deliberately small Markdown subset used by the renderer."""
    tokens = []
    index = 0
    markers = (("__", "underline"), ("~~", "highlight"), ("*", "italic"))
    while index < len(line):
        ref = re.match(r"\[\^([^\]]+)\]", line[index:])
        if ref:
            tokens.append({"style": "reference", "text": ref.group(1)})
            index += ref.end()
            continue
        matched = False
        for marker, style in markers:
            if line.startswith(marker, index):
                end = line.find(marker, index + len(marker))
                if end > index + len(marker):
                    tokens.append({"style": style, "text": line[index + len(marker):end]})
                    index = end + len(marker)
                    matched = True
                    break
        if matched:
            continue
        next_positions = []
        for marker, _ in markers:
            pos = line.find(marker, index + 1)
            if pos >= 0:
                next_positions.append(pos)
        ref_pos = line.find("[^", index + 1)
        if ref_pos >= 0:
            next_positions.append(ref_pos)
        end = min(next_positions) if next_positions else len(line)
        tokens.append({"style": "plain", "text": line[index:end]})
        index = end
    return tokens


def _parse_markdown_document(text: str):
    footnotes = {}
    body_lines = []
    for line in text.splitlines():
        definition = re.match(r"^\[\^([^\]]+)\]:\s*(.*)$", line)
        if definition:
            footnotes[definition.group(1)] = definition.group(2).strip()
        else:
            body_lines.append(_parse_inline_markdown(line))
    if not body_lines:
        body_lines = [[]]
    return body_lines, footnotes


def _wrap_styled_lines(draw, source_lines, font, reference_font, max_width):
    wrapped = []
    for source in source_lines:
        current = []
        current_width = 0
        if not source:
            wrapped.append([])
            continue
        for token in source:
            style = token["style"]
            if style == "reference":
                display = f"[{token['text']}]"
                width = draw.textbbox((0, 0), display, font=reference_font)[2]
                if current and current_width + width > max_width:
                    wrapped.append(current)
                    current, current_width = [], 0
                current.append({"style": style, "text": token["text"]})
                current_width += width
                continue
            for char in token["text"]:
                width = draw.textbbox((0, 0), char, font=font)[2]
                if current and current_width + width > max_width:
                    wrapped.append(current)
                    current, current_width = [], 0
                    if char.isspace():
                        continue
                if current and current[-1]["style"] == style:
                    current[-1]["text"] += char
                else:
                    current.append({"style": style, "text": char})
                current_width += width
        wrapped.append(current)
    return wrapped


def _draw_italic_text(canvas, xy, text, font, fill):
    """Draw synthetic italic text so Korean fonts without italic faces still work."""
    if not text:
        return
    bbox = font.getbbox(text)
    width = max(1, bbox[2] + 8)
    height = max(1, bbox[3] + 8)
    shear = 0.20
    shift = int(height * shear) + 4
    layer = Image.new("RGBA", (width + shift, height), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((2, 0), text, font=font, fill=fill)
    slanted = layer.transform(
        layer.size,
        Image.Transform.AFFINE,
        (1, shear, -shear * height, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    canvas.alpha_composite(slanted, (int(xy[0]), int(xy[1])))


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
                "font_path": ("STRING", {"default": "AUTO"}),
                "comment_font_path": ("STRING", {"default": "AUTO"}),
                "text_color": ("STRING", {"default": "#202020"}),
                "pencil_color": ("STRING", {"default": "#C63B3B"}),
                "highlight_color": ("STRING", {"default": "#FFF176"}),
                "background_color": ("STRING", {"default": "#FFFDF7"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("annotated_page",)
    FUNCTION = "render_book_page"
    CATEGORY = "Korean OCR"

    def render_book_page(self, text, comment, width, font_size, comment_font_size, padding,
                         line_spacing, font_path, comment_font_path, text_color,
                         pencil_color, highlight_color, background_color):
        font, _ = _load_font(font_path, font_size)
        comment_font, _ = _load_handwriting_font(comment_font_path, comment_font_size)
        scratch = Image.new("RGB", (width, 64), "white")
        measure = ImageDraw.Draw(scratch)
        usable_width = max(1, width - 2 * padding)

        reference_font, _ = _load_font(font_path, max(12, int(font_size * 0.55)))
        source_lines, footnotes = _parse_markdown_document(text)
        lines = _wrap_styled_lines(measure, source_lines, font, reference_font, usable_width)

        referenced_ids = []
        for line in lines:
            for token in line:
                if token["style"] == "reference" and token["text"] not in referenced_ids:
                    referenced_ids.append(token["text"])
        note_sources = []
        for ref_id in referenced_ids:
            if footnotes.get(ref_id):
                note_sources.append(f"[{ref_id}] {footnotes[ref_id]}")
        if comment.strip():
            note_sources.extend(comment.splitlines())
        comment_lines = []
        for source in note_sources:
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

        for line_index, line in enumerate(lines):
            x = padding
            for token in line:
                style, value = token["style"], token["text"]
                if style == "reference":
                    display = f"[{value}]"
                    draw.text(
                        (x, y - 3), display, font=reference_font,
                        fill=(190, 38, 45, 235),
                    )
                    x += measure.textbbox((0, 0), display, font=reference_font)[2]
                    continue
                span_width = measure.textbbox((0, 0), value, font=font)[2]
                if style == "highlight" and value:
                    top = y + int(main_height * 0.46)
                    bottom = y + main_height + 5
                    draw.rounded_rectangle(
                        (x - 5, top, x + span_width + 7, bottom),
                        radius=max(3, font_size // 7),
                        fill=highlight_rgb + (96,),
                    )
                if style == "italic":
                    _draw_italic_text(canvas, (x, y), value, font, text_fill)
                else:
                    draw.text((x, y), value, font=font, fill=text_fill)
                if style == "underline" and value:
                    baseline = y + main_height + 7
                    offsets = ((0, 0, 90), (2, 1, 65), (-1, 3, 45))
                    for dx, dy, alpha in offsets:
                        points = []
                        segments = max(2, span_width // 24)
                        for step in range(segments + 1):
                            px = x + dx + (span_width * step / segments)
                            jitter = ((step * 7 + line_index * 3) % 5) - 2
                            points.append((px, baseline + dy + jitter * 0.35))
                        draw.line(points, fill=pencil_rgb + (alpha,), width=max(1, font_size // 25))
                x += span_width
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
    "KoreanOCRAutoCorrect": KoreanOCRAutoCorrect,
    "KoreanTextStyleSettings": KoreanTextStyleSettings,
    "KoreanEditableText": KoreanEditableText,
    "KoreanTextToImage": KoreanTextToImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KoreanOCR": "한국어 OCR (PaddleOCR)",
    "KoreanMaskedOCR": "마스크 영역 한국어 OCR",
    "KoreanOCRAutoCorrect": "로컬 AI OCR 교정 + 꾸밈 추천",
    "KoreanTextStyleSettings": "글꼴·색상·크기 설정 + 미리보기",
    "KoreanEditableText": "OCR 텍스트 수정 → 이미지",
    "KoreanTextToImage": "한국어 텍스트 → 이미지",
}

WEB_DIRECTORY = "./comfyui_korean_ocr_web"
