# ComfyUI 한국어 OCR → 텍스트 이미지

입력 이미지에서 마스크로 칠한 부분만 PaddleOCR로 읽고, 추출 문장을 수정한 뒤 밑줄·형광펜·필기 코멘트가 들어간 PNG로 렌더링합니다.

## 설치

1. `comfyui_korean_ocr_to_image.py`와 `comfyui_korean_ocr_web` 폴더를 `ComfyUI/custom_nodes/`에 복사합니다.
2. ComfyUI가 사용하는 Python에 PaddleOCR를 설치합니다.

일반 설치판:

```powershell
cd C:\경로\ComfyUI
python -m pip install paddlepaddle paddleocr
```

Windows portable판:

```powershell
cd C:\경로\ComfyUI_windows_portable
.\python_embeded\python.exe -m pip install paddlepaddle paddleocr
```

3. ComfyUI를 완전히 재시작합니다.
4. `korean_ocr_to_image.workflow.json`을 ComfyUI 화면에 드래그하거나 `Ctrl+O`로 엽니다.
5. `Load Image`에서 실제 이미지를 선택하고 Queue를 실행합니다. 첫 실행 때 한국어 OCR 모델을 내려받으므로 시간이 걸릴 수 있습니다.

## 마스크 → 수정 → 꾸미기

1. `Load Image`를 우클릭하고 `Open in Mask Editor`를 선택합니다.
2. OCR할 문단만 흰색으로 칠하고 저장합니다.
3. Queue를 한 번 실행하면 `OCR 텍스트 수정`의 편집 칸에 인식 결과가 자동 입력됩니다.
4. 오탈자와 줄바꿈을 직접 수정하고 코멘트를 입력합니다.
5. 다시 Queue하면 수정본으로 이미지가 저장됩니다.
6. 새 OCR 결과로 되돌리려면 `OCR 원문으로 재설정` 버튼을 누릅니다.

꾸밀 부분은 다음 Markdown형 문법으로 지정합니다.

```markdown
__이 부분은 색연필 밑줄__[^1]
*이 부분은 이탤릭*
~~이 부분은 형광펜~~

[^1]: 밑줄 친 문장에 다는 붉은 손글씨 코멘트
```

각주 정의는 본문에서 제거되고 이미지 아래에 더 작은 붉은 손글씨로 표시됩니다. 별도의 `comment` 입력은 특정 밑줄에 연결하지 않는 일반 메모로 계속 사용할 수 있습니다.

## 소설책 촬영 권장값

- `detect_rotation`: `true`
- `document_unwarp`: `true` — 휘어진 페이지와 원근을 보정합니다(PaddleOCR 3.x).
- `enhance_book_photo`: `true` — 회색조, 자동 대비, 약한 선명화와 저해상도 확대를 적용합니다.
- 한 장에 양쪽 페이지가 같이 찍혔고 읽기 순서가 섞이면, 왼쪽/오른쪽 페이지를 각각 잘라 두 번 처리하는 편이 정확합니다.
- 그림자나 페이지 휨이 심하면 책등과 카메라를 평행하게 하고, 페이지 전체에 빛이 고르게 들어오도록 다시 촬영하는 것이 가장 효과적입니다.

## 폰트

- Windows에서는 `AUTO`가 기본적으로 `C:\Windows\Fonts\malgun.ttf`(맑은 고딕)를 사용합니다.
- 글자가 네모로 나오거나 폰트를 못 찾으면 `font_path`에 한글을 지원하는 `.ttf`/`.ttc` 절대 경로를 넣습니다.
- 예: `C:\Windows\Fonts\malgun.ttf`

## 생성형 text-to-image로 연결하려면

`한국어 OCR (PaddleOCR)`의 `korean_text` 출력을 체크포인트 워크플로의 `CLIP Text Encode (Prompt)`의 `text` 입력에 연결하면 됩니다. 모델에 따라 한국어 프롬프트 이해도가 낮을 수 있으므로, 그 경우 OCR과 CLIP 사이에 번역 노드를 추가하세요.

## 문제 해결

- `No module named paddleocr`: ComfyUI가 실제로 사용하는 Python에 설치했는지 확인합니다.
- Paddle 관련 DLL 오류: ComfyUI를 종료한 뒤 `paddlepaddle`을 다시 설치하고 재시작합니다.
- `ConvertPirAttribute2RuntimeAttribute` 오류: 이 노드는 Windows의 Paddle 3.3.x oneDNN 문제를 피하도록 `enable_mkldnn=False`를 적용합니다. 이전 파일을 설치했다면 최신 파일로 덮어쓰세요.
- 같은 문장이 여러 번 출력됨: 복잡한 표/문서에서는 OCR 레이아웃 결과가 중복될 수 있습니다. 원본을 문단 단위로 잘라 입력하면 안정적입니다.
