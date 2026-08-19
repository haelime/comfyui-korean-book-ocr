# ComfyUI Korean Book OCR

Photographed Korean book page → painted mask region only → local-AI correction → editable OCR text → styled quote image.

한국어 소설책 촬영본에서 원하는 문단만 마스킹해 OCR하고, 인식 결과를 직접 수정한 뒤 색연필 밑줄·형광펜·붉은 손글씨 코멘트가 들어간 이미지로 저장하는 ComfyUI 커스텀 노드입니다.

## Documentation

- [한국어 초보자 설치 가이드](docs/INSTALL.ko.md)
- [한국어 워크플로우 사용법](docs/WORKFLOW.ko.md)
- [한국어 전체 README](README.ko.md)
- [함께 쓰기 좋은 유틸리티 노드](UTILITY_NODES.md)

## Nodes

- **마스크 영역 한국어 OCR** — crops and recognizes only the painted mask region.
- **로컬 AI OCR 교정 + 꾸밈 추천** — performs a two-pass typo review and sends a Qwen-recommended Markdown decoration version to the editor while exposing plain correction and OCR source outputs.
- **글꼴·색상·크기 설정 + 미리보기** — centralizes all visual parameters and renders a live preview image.
- **OCR 텍스트 수정 → 이미지** — edits OCR text and directly renders Markdown-like italic, highlighter, colored-pencil underline, and footnote comments.
- **한국어 OCR / 한국어 텍스트 → 이미지** — simpler reusable OCR and text rendering nodes.

## Quick install

Clone into `ComfyUI/custom_nodes` and install requirements with ComfyUI's Python environment.

```powershell
cd ComfyUI\custom_nodes
git clone https://github.com/haelime/comfyui-korean-book-ocr.git
cd comfyui-korean-book-ocr
uv pip install --python ..\..\.venv\Scripts\python.exe -r requirements.txt
```

Restart ComfyUI. Load `korean_ocr_to_image.workflow.json` from this repository or from the workflow menu after copying it into `user/default/workflows`.

For Desktop, portable, ZIP, and troubleshooting instructions, follow the [step-by-step Korean installation guide](docs/INSTALL.ko.md).

Install and run [Ollama](https://ollama.com), then download the default local model:

```powershell
ollama pull qwen3:8b
```

## Use

1. Select a book photo in `Load Image`.
2. Leave the mask empty to OCR the whole image, or open **Mask Editor** to select only part of it.
3. If using a mask, paint the paragraph to recognize and save it.
4. Queue once. Ollama performs precise typo correction and sends its Markdown recommendation to **OCR 텍스트 수정 → 이미지**.
5. Set fonts, sizes, and colors in **글꼴·색상·크기 설정 + 미리보기**. The default pencil underline is red.
6. Correct text or add Markdown styles, then queue again to render and save.

## Inline style syntax

```markdown
__colored-pencil underline__[^1]
*synthetic italic*
~~highlighter~~

[^1]: A smaller red handwritten comment attached to the underlined phrase.
```

Underline, italic, and highlighter markers may open on one source line and close on another.

각주 문법은 `__밑줄__[^id]`와 `[^id]: 코멘트`를 함께 사용합니다. Footnote definitions are removed from the main body and rendered below it in smaller red handwriting.

For a flat page, keep `document_unwarp=false`. Enable it for a visibly curved page. If the mask direction is reversed, enable `invert_mask`.

See [README.ko.md](README.ko.md) for detailed Korean instructions and [UTILITY_NODES.md](UTILITY_NODES.md) for optional companion node packs.

## Notes

- Windows automatically uses Malgun Gothic for the main text when available.
- The footnote renderer tries common Korean handwriting fonts first, then falls back to a Korean system font.
- `enable_mkldnn=False` is intentional: it avoids a Paddle 3.3.x oneDNN/PIR inference failure seen on Windows CPU execution.
- OCR models are downloaded by PaddleOCR on first use.

## License

MIT
