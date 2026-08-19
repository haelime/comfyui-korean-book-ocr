# ComfyUI Korean Book OCR

Photographed Korean book page → painted mask region only → editable OCR text → styled quote image.

한국어 소설책 촬영본에서 원하는 문단만 마스킹해 OCR하고, 인식 결과를 직접 수정한 뒤 색연필 밑줄·형광펜·붉은 손글씨 코멘트가 들어간 이미지로 저장하는 ComfyUI 커스텀 노드입니다.

## Nodes

- **마스크 영역 한국어 OCR** — crops and recognizes only the painted mask region.
- **OCR 텍스트 수정** — automatically fills an editable multiline widget after OCR; user corrections are preserved.
- **책 문장 꾸미기 → 이미지** — renders highlighter, colored-pencil underline, and a smaller red handwritten comment.
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

## Use

1. Select a book photo in `Load Image`.
2. Right-click the node and open **Mask Editor**.
3. Paint only the paragraph to recognize and save the mask.
4. Queue once. The recognized text appears in **OCR 텍스트 수정**.
5. Correct OCR mistakes and line breaks. Add a short comment in the renderer.
6. Queue again to render and save the annotated quote image.

For a flat page, keep `document_unwarp=false`. Enable it for a visibly curved page. If the mask direction is reversed, enable `invert_mask`.

See [README.ko.md](README.ko.md) for detailed Korean instructions and [UTILITY_NODES.md](UTILITY_NODES.md) for optional companion node packs.

## Notes

- Windows automatically uses Malgun Gothic for the main text when available.
- The comment renderer tries common Korean handwriting fonts first, then falls back to a Korean system font.
- `enable_mkldnn=False` is intentional: it avoids a Paddle 3.3.x oneDNN/PIR inference failure seen on Windows CPU execution.
- OCR models are downloaded by PaddleOCR on first use.

## License

MIT

