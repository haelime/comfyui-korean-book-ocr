"""ComfyUI nodes: Korean OCR and Unicode text-to-image rendering.

Copy this file to ComfyUI/custom_nodes and restart ComfyUI.
Install the optional OCR dependencies into ComfyUI's Python environment:
    python -m pip install paddlepaddle paddleocr
"""

from __future__ import annotations

import os
import re
import json
import hashlib
import random
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

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
    if not (alpha > 0.05).any():
        return rgb.copy()
    if invert:
        alpha = 1.0 - alpha
    selected = alpha > 0.05
    if not selected.any():
        return rgb.copy()
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


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def _comfy_directory(kind: str) -> Path:
    """Return a ComfyUI data directory without requiring ComfyUI during tests."""
    try:
        import folder_paths

        getters = {
            "input": folder_paths.get_input_directory,
            "output": folder_paths.get_output_directory,
        }
        return Path(getters[kind]()).resolve()
    except (ImportError, AttributeError, KeyError):
        return (Path.cwd() / kind).resolve()


def _resolve_batch_folder(value: str, kind: str, create: bool = False) -> Path:
    cleaned = os.path.expandvars(os.path.expanduser(value.strip().strip('"')))
    if not cleaned:
        raise ValueError("폴더 이름을 입력하세요.")
    folder = Path(cleaned)
    if not folder.is_absolute():
        folder = _comfy_directory(kind) / folder
    folder = folder.resolve()
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def _batch_files(folder: Path, extensions: set[str]):
    return sorted(
        (path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in extensions),
        key=lambda path: str(path.relative_to(folder)).casefold(),
    )


def _atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _batch_target(source: Path, source_root: Path, output_root: Path, suffix: str, claimed: set[Path]):
    relative = source.relative_to(source_root)
    target = (output_root / relative).with_suffix(suffix)
    if target in claimed:
        target = target.with_name(f"{target.stem}_{source.suffix[1:].lower()}{suffix}")
    claimed.add(target)
    return target


class KoreanOCRAutoCorrect:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "OCR_텍스트": ("STRING", {"forceInput": True}),
                "자동_교정": ("BOOLEAN", {"default": True}),
                "모델": ("STRING", {"default": "qwen3:8b"}),
                "교정_강도": (["정밀", "보수적", "일반"], {"default": "정밀"}),
                "고유명사_보존": ("BOOLEAN", {"default": True}),
                "올라마_주소": ("STRING", {"default": "http://127.0.0.1:11434"}),
                "제한_시간_초": ("INT", {"default": 180, "min": 10, "max": 1800}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("교정_텍스트", "OCR_원문")
    FUNCTION = "교정"
    CATEGORY = "한국어 OCR"

    def 교정(self, OCR_텍스트, 자동_교정, 모델, 교정_강도, 고유명사_보존,
             올라마_주소, 제한_시간_초):
        if not 자동_교정 or not OCR_텍스트.strip():
            return (OCR_텍스트, OCR_텍스트)

        if 교정_강도 == "정밀":
            strength = (
                "원문과 글자 단위로 대조해 음절 누락·중복, 비슷한 글자 오인식, 잘못된 받침과 "
                "활용, 부사형 -이/-히, 띄어쓰기·문장부호·따옴표를 문맥으로 점검하라. "
                "확실한 오타는 빠짐없이 고치되 "
                "작가의 문체, 방언, 옛말, 의도적인 비문은 함부로 표준어로 바꾸지 마라."
            )
        elif 교정_강도 == "보수적":
            strength = "명백한 OCR 오인식, 띄어쓰기, 문장부호만 고치고 문체와 어휘는 바꾸지 마라."
        else:
            strength = "OCR 오인식과 맞춤법을 고치되 원문의 의미와 문체를 유지하라."
        proper_nouns = (
            "사람 이름, 지명, 작품명 등 고유명사는 확실한 근거가 없으면 절대 바꾸지 마라."
            if 고유명사_보존 else "문맥상 명백히 잘못 인식된 고유명사는 교정해도 된다."
        )
        correction_prompt = (
            "다음은 한국어 소설책 사진에서 추출한 OCR 텍스트다.\n"
            f"{strength}\n{proper_nouns}\n"
            "문단과 줄바꿈을 가능한 한 보존하고, 내용을 추가·요약·번역하지 마라. "
            "corrected_text에는 Markdown 없는 순수 교정문만 넣어라.\n\n"
            f"OCR 원문:\n{OCR_텍스트}"
        )
        correction_schema = {
            "type": "object",
            "properties": {"corrected_text": {"type": "string"}},
            "required": ["corrected_text"],
        }
        model_name = 모델.strip() or "qwen3:8b"

        def request_json(prompt, schema):
            payload = json.dumps({
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "format": schema,
                "options": {"temperature": 0},
            }, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(
                올라마_주소.rstrip("/") + "/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=제한_시간_초) as response:
                result = json.loads(response.read().decode("utf-8"))
            return json.loads(result.get("response", "{}"))

        try:
            corrected = request_json(correction_prompt, correction_schema)["corrected_text"].strip()
            corrected = corrected or OCR_텍스트

            if 교정_강도 == "정밀":
                review_prompt = (
                    "너는 두 번째 한국어 교정자다. 아래 문장은 1차 OCR 교정을 마친 결과다. "
                    "독립 검수하여 남은 음절 누락·중복, 받침, 활용, 부사형 -이/-히, 띄어쓰기, "
                    "문장부호 오류를 찾아라. 특히 자연스럽게 읽혀 지나치기 쉬운 오타도 문맥으로 "
                    "확인하라. 내용과 문체는 바꾸지 말고 corrected_text JSON만 출력하라.\n\n"
                    f"1차 교정문:\n{corrected}"
                )
                reviewed = request_json(review_prompt, correction_schema)["corrected_text"].strip()
                corrected = reviewed or corrected

        except urllib.error.URLError as exc:
            raise RuntimeError(
                "로컬 AI(Ollama)에 연결하지 못했습니다. Ollama가 실행 중인지 확인하세요: "
                f"{올라마_주소}"
            ) from exc
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError("로컬 AI 교정 결과를 읽지 못했습니다. 다시 실행해 주세요.") from exc
        return (corrected, OCR_텍스트)


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
            "__붉은 색연필 밑줄__[^1]  **굵게**  *이탤릭*  ~~형광펜~~\n\n"
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
    markers = (("**", "bold"), ("__", "underline"), ("~~", "highlight"), ("*", "italic"))
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
    body_source = []
    for line in text.splitlines():
        definition = re.match(r"^\[\^([^\]]+)\]:\s*(.*)$", line)
        if definition:
            footnotes[definition.group(1)] = definition.group(2).strip()
        else:
            body_source.append(line)

    # Parse the body as one string so a marker can open on one source line and
    # close on another. Split the styled tokens back into source lines after
    # parsing; this preserves both explicit line breaks and the active style.
    flat_tokens = _parse_inline_markdown("\n".join(body_source))
    body_lines = [[]]
    for token in flat_tokens:
        if token["style"] == "reference":
            body_lines[-1].append(token)
            continue
        parts = token["text"].split("\n")
        for index, part in enumerate(parts):
            if part:
                if body_lines[-1] and body_lines[-1][-1]["style"] == token["style"]:
                    body_lines[-1][-1]["text"] += part
                else:
                    body_lines[-1].append({"style": token["style"], "text": part})
            if index < len(parts) - 1:
                body_lines.append([])
    return body_lines or [[]], footnotes


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


def _draw_colored_pencil_underline(draw, x, baseline, span_width, color, font_size, seed_text):
    """Draw a deterministic multi-strand underline with waxy pencil grain."""
    if span_width <= 0:
        return
    seed = int.from_bytes(
        hashlib.blake2b(seed_text.encode("utf-8"), digest_size=8).digest(), "big"
    )
    rng = random.Random(seed)
    stroke_width = max(1, font_size // 30)

    # Sparse pigment dust makes the edge feel dry without blurring the text.
    grain_count = max(8, span_width // 7)
    for _ in range(grain_count):
        px = x + rng.uniform(0, span_width)
        py = baseline + rng.uniform(-3.8, 4.2)
        radius = rng.choice((0.35, 0.5, 0.8, 1.0))
        alpha = rng.randint(18, 48)
        draw.ellipse(
            (px - radius, py - radius, px + radius, py + radius),
            fill=color + (alpha,),
        )

    # Several imperfect strands create visible tooth and tiny paper gaps.
    strand_settings = ((-1.3, 58), (0.2, 102), (1.5, 50))
    for strand_index, (offset, base_alpha) in enumerate(strand_settings):
        cursor = 0.0
        previous_y = baseline + offset + rng.uniform(-0.7, 0.7)
        while cursor < span_width:
            segment = min(rng.uniform(4.0, 12.0), span_width - cursor)
            gap = rng.uniform(0.4, 2.6) if rng.random() < 0.32 else rng.uniform(0.0, 0.7)
            end = max(cursor, min(span_width, cursor + segment - gap))
            next_y = baseline + offset + rng.uniform(-1.2, 1.2)
            if end > cursor and rng.random() > 0.08:
                pressure = rng.uniform(0.72, 1.28)
                alpha = max(18, min(145, round(base_alpha * pressure)))
                draw.line(
                    ((x + cursor, previous_y), (x + end, next_y)),
                    fill=color + (alpha,),
                    width=stroke_width + (1 if strand_index == 1 and pressure > 1.08 else 0),
                )
            cursor += segment
            previous_y = next_y

    # Short darker deposits imitate places where hand pressure increased.
    deposit_count = max(1, span_width // 110)
    for _ in range(deposit_count):
        start = rng.uniform(0, max(0, span_width - 12))
        length = min(rng.uniform(7, 24), span_width - start)
        y1 = baseline + rng.uniform(-0.8, 0.8)
        y2 = y1 + rng.uniform(-0.5, 0.5)
        draw.line(
            ((x + start, y1), (x + start + length, y2)),
            fill=color + (rng.randint(105, 155),),
            width=stroke_width,
        )


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
                elif style == "bold":
                    draw.text(
                        (x, y), value, font=font, fill=text_fill,
                        stroke_width=max(1, font_size // 32), stroke_fill=text_fill,
                    )
                else:
                    draw.text((x, y), value, font=font, fill=text_fill)
                if style == "underline" and value:
                    baseline = y + main_height + 7
                    _draw_colored_pencil_underline(
                        draw,
                        x,
                        baseline,
                        span_width,
                        pencil_rgb,
                        font_size,
                        f"{line_index}:{value}",
                    )
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


class KoreanBatchImagesToText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "실행": ("BOOLEAN", {"default": True}),
                "사진_폴더": ("STRING", {"default": "대량_OCR_사진"}),
                "텍스트_저장_폴더": ("STRING", {"default": "korean_book_ocr/text"}),
                "기존_텍스트_보호": ("BOOLEAN", {"default": True}),
                "문서_펴기": ("BOOLEAN", {"default": False}),
                "자동_맞춤법_교정": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("작업_결과", "텍스트_폴더")
    FUNCTION = "process_folder"
    CATEGORY = "한국어 OCR/대량 작업"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def process_folder(self, 실행, 사진_폴더, 텍스트_저장_폴더, 기존_텍스트_보호,
                       문서_펴기, 자동_맞춤법_교정):
        input_folder = _resolve_batch_folder(사진_폴더, "input", create=True)
        output_folder = _resolve_batch_folder(텍스트_저장_폴더, "output", create=True)
        if not 실행:
            summary = "1단계가 꺼져 있습니다. 사진 OCR을 시작하려면 실행을 켜세요."
            return {"ui": {"text": [summary]}, "result": (summary, str(output_folder))}

        sources = _batch_files(input_folder, _IMAGE_EXTENSIONS)
        if not sources:
            summary = f"사진이 없습니다. 이 폴더에 사진을 넣으세요:\n{input_folder}"
            return {"ui": {"text": [summary]}, "result": (summary, str(output_folder))}

        ocr_node = KoreanOCR()
        correction_node = KoreanOCRAutoCorrect()
        claimed = set()
        completed, skipped, warnings, errors = [], [], [], []
        for source in sources:
            target = _batch_target(source, input_folder, output_folder, ".txt", claimed)
            if 기존_텍스트_보호 and target.exists():
                skipped.append(target)
                continue
            try:
                with Image.open(source) as opened:
                    rgb = np.asarray(opened.convert("RGB"), dtype=np.float32) / 255.0
                tensor = torch.from_numpy(rgb).unsqueeze(0)
                raw_text = ocr_node.recognize(
                    tensor, "PP-OCRv5", True, 문서_펴기, True,
                )[0]
                final_text = raw_text
                if 자동_맞춤법_교정 and raw_text.strip():
                    try:
                        final_text = correction_node.교정(
                            raw_text, True, "qwen3:8b", "정밀", True,
                            "http://127.0.0.1:11434", 180,
                        )[0]
                    except Exception as exc:
                        warnings.append(f"{source.name}: AI 교정을 건너뛰고 OCR 원문 저장 ({exc})")
                _atomic_write_text(target, final_text.rstrip() + "\n")
                completed.append(target)
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")

        lines = [
            f"사진 {len(sources)}개 확인",
            f"텍스트 {len(completed)}개 생성",
            f"기존 파일 {len(skipped)}개 보호",
            f"AI 교정 경고 {len(warnings)}개",
            f"오류 {len(errors)}개",
            f"저장 위치: {output_folder}",
        ]
        if warnings:
            lines.extend(["", "경고 목록:", *warnings])
        if errors:
            lines.extend(["", "오류 목록:", *errors])
        summary = "\n".join(lines)
        return {"ui": {"text": [summary]}, "result": (summary, str(output_folder))}


class KoreanBatchTextToImages:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "스타일_설정": ("KOREAN_TEXT_STYLE", {"forceInput": True}),
                "실행": ("BOOLEAN", {"default": False}),
                "텍스트_폴더": ("STRING", {"forceInput": True}),
                "이미지_저장_폴더": ("STRING", {"default": "korean_book_ocr/images"}),
                "기존_이미지_덮어쓰기": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("작업_결과", "마지막_이미지")
    FUNCTION = "render_folder"
    CATEGORY = "한국어 OCR/대량 작업"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    @staticmethod
    def _blank_preview(style):
        color = ImageColor.getrgb(style["background_color"])
        image = np.full((128, 256, 3), color, dtype=np.uint8)
        return torch.from_numpy(image.astype(np.float32) / 255.0).unsqueeze(0)

    def render_folder(self, 스타일_설정, 실행, 텍스트_폴더, 이미지_저장_폴더,
                      기존_이미지_덮어쓰기):
        input_folder = _resolve_batch_folder(텍스트_폴더, "output", create=True)
        output_folder = _resolve_batch_folder(이미지_저장_폴더, "output", create=True)
        preview = self._blank_preview(스타일_설정)
        if not 실행:
            summary = "2단계가 꺼져 있습니다. 텍스트 수정을 마친 뒤 실행을 켜세요."
            return {"ui": {"text": [summary]}, "result": (summary, preview)}

        sources = _batch_files(input_folder, {".txt"})
        if not sources:
            summary = f"텍스트 파일이 없습니다. 먼저 1단계를 실행하세요:\n{input_folder}"
            return {"ui": {"text": [summary]}, "result": (summary, preview)}

        renderer = KoreanBookTextToImage()
        style = 스타일_설정
        claimed = set()
        completed, skipped, errors = [], [], []
        for source in sources:
            target = _batch_target(source, input_folder, output_folder, ".png", claimed)
            if not 기존_이미지_덮어쓰기 and target.exists():
                skipped.append(target)
                continue
            try:
                text = source.read_text(encoding="utf-8-sig")
                preview = renderer.render_book_page(
                    text, "", style["width"], style["font_size"],
                    style["comment_font_size"], style["padding"], style["line_spacing"],
                    style["font_path"], style["comment_font_path"], style["text_color"],
                    style["pencil_color"], style["highlight_color"], style["background_color"],
                )[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(_tensor_to_rgb(preview)).save(target, format="PNG")
                completed.append(target)
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")

        lines = [
            f"텍스트 {len(sources)}개 확인",
            f"이미지 {len(completed)}개 생성",
            f"기존 이미지 {len(skipped)}개 건너뜀",
            f"오류 {len(errors)}개",
            f"저장 위치: {output_folder}",
        ]
        if errors:
            lines.extend(["", "오류 목록:", *errors])
        summary = "\n".join(lines)
        return {"ui": {"text": [summary]}, "result": (summary, preview)}


NODE_CLASS_MAPPINGS = {
    "KoreanOCR": KoreanOCR,
    "KoreanMaskedOCR": KoreanMaskedOCR,
    "KoreanOCRAutoCorrect": KoreanOCRAutoCorrect,
    "KoreanTextStyleSettings": KoreanTextStyleSettings,
    "KoreanEditableText": KoreanEditableText,
    "KoreanTextToImage": KoreanTextToImage,
    "KoreanBatchImagesToText": KoreanBatchImagesToText,
    "KoreanBatchTextToImages": KoreanBatchTextToImages,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KoreanOCR": "한국어 OCR (PaddleOCR)",
    "KoreanMaskedOCR": "마스크 영역 한국어 OCR",
    "KoreanOCRAutoCorrect": "로컬 AI OCR 오타·맞춤법 교정",
    "KoreanTextStyleSettings": "글꼴·색상·크기 설정 + 미리보기",
    "KoreanEditableText": "OCR 텍스트 수정 → 이미지",
    "KoreanTextToImage": "한국어 텍스트 → 이미지",
    "KoreanBatchImagesToText": "① 사진 폴더 → OCR 텍스트 파일",
    "KoreanBatchTextToImages": "② 텍스트 폴더 → 파일별 이미지",
}

WEB_DIRECTORY = "./comfyui_korean_ocr_web"
