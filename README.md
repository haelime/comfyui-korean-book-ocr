# ComfyUI Korean Book OCR

Photographed Korean book page → painted mask region only → local-AI correction → editable OCR text → styled quote image.

한국어 소설책 촬영본에서 원하는 문단만 마스킹해 OCR하고, 인식 결과를 직접 수정한 뒤 색연필 밑줄·형광펜·붉은 손글씨 코멘트가 들어간 이미지로 저장하는 ComfyUI 커스텀 노드입니다.

## Nodes

- **마스크 영역 한국어 OCR** — crops and recognizes only the painted mask region.
- **로컬 AI OCR 자동 교정** — conservatively corrects OCR errors through a local Ollama model.
- **글꼴·색상·크기 설정 + 미리보기** — centralizes all visual parameters and renders a live preview image.
- **OCR 텍스트 수정 → 이미지** — edits OCR text and directly renders Markdown-like italic, highlighter, colored-pencil underline, and footnote comments.
- **한국어 OCR / 한국어 텍스트 → 이미지** — simpler reusable OCR and text rendering nodes.

## Install

Clone into `ComfyUI/custom_nodes` and install requirements with ComfyUI's Python environment.

```powershell
cd ComfyUI\custom_nodes
git clone https://github.com/haelime/comfyui-korean-book-ocr.git
cd comfyui-korean-book-ocr
uv pip install --python ..\..\.venv\Scripts\python.exe -r requirements.txt
```

Restart ComfyUI. Load `korean_ocr_to_image.workflow.json` from this repository or from the workflow menu after copying it into `user/default/workflows`.

Install and run [Ollama](https://ollama.com), then download the default local model:

```powershell
ollama pull qwen3:8b
```

## Use

1. Select a book photo in `Load Image`.
2. Right-click the node and open **Mask Editor**.
3. Paint only the paragraph to recognize and save the mask.
4. Queue once. Ollama corrects OCR errors and the result appears in **OCR 텍스트 수정 → 이미지**.
5. Set fonts, sizes, and colors in **글꼴·색상·크기 설정 + 미리보기**. The default pencil underline is red.
6. Correct text or add Markdown styles, then queue again to render and save.

## Inline style syntax

```markdown
__colored-pencil underline__[^1]
*synthetic italic*
~~highlighter~~

[^1]: A smaller red handwritten comment attached to the underlined phrase.
```

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
