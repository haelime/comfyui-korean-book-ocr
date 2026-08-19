# ComfyUI 한국어 OCR → 텍스트 이미지

입력 이미지에서 마스크로 칠한 부분만 PaddleOCR로 읽고, 로컬 AI로 오인식을 교정한 뒤 밑줄·형광펜·필기 코멘트가 들어간 PNG로 렌더링합니다.

## 문서 바로가기

- [처음부터 따라 하는 Windows 설치 가이드](docs/INSTALL.ko.md)
- [워크플로우와 Qwen 추천 선택 사용법](docs/WORKFLOW.ko.md)
- [함께 쓰기 좋은 유틸리티 노드](UTILITY_NODES.md)

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

## 로컬 AI 자동 교정 설치

Ollama를 설치하고 다음 모델을 한 번 내려받습니다. 모든 교정은 PC 안에서 처리되며 OCR 문장이 외부 서비스로 전송되지 않습니다.

```powershell
ollama pull qwen3:8b
```

워크플로우의 `로컬 AI OCR 교정 + 꾸밈 추천` 노드는 교정문과 Markdown 꾸밈 추천문을 동시에 만듭니다. `꾸밈_선택`에서 `자동 추천 사용` 또는 `추천 없이 교정만`을 고를 수 있습니다. `교정_텍스트`와 `꾸밈_추천_텍스트` 출력도 따로 제공하므로 필요하면 다른 텍스트 노드에 연결해 비교할 수 있습니다. AI를 사용하지 않을 때는 `자동_교정`을 끄면 OCR 원문을 그대로 통과시킵니다.

## 마스크 → 수정 및 이미지 생성

1. `Load Image`를 우클릭하고 `Open in Mask Editor`를 선택합니다.
2. OCR할 문단만 흰색으로 칠하고 저장합니다.
3. Queue를 한 번 실행하면 로컬 AI가 오인식을 교정하고 선택한 꾸밈 추천 여부에 따라 `OCR 텍스트 수정 → 이미지`의 편집 칸에 결과를 자동 입력합니다.
4. 같은 노드에서 오탈자·줄바꿈·Markdown 꾸밈·코멘트를 수정합니다.
5. 다시 Queue하면 이 노드가 수정본을 바로 이미지로 만들어 저장합니다.
6. 직접 수정한 내용을 현재 선택한 AI 결과로 되돌리려면 `AI 선택본으로 재설정` 버튼을 누릅니다.

꾸밀 부분은 다음 Markdown형 문법으로 지정합니다.

```markdown
__이 부분은 색연필 밑줄__[^1]
*이 부분은 이탤릭*
~~이 부분은 형광펜~~

[^1]: 밑줄 친 문장에 다는 붉은 손글씨 코멘트
```

각주 정의는 본문에서 제거되고 이미지 아래에 더 작은 붉은 손글씨로 표시됩니다.

## 글꼴·색상·크기 설정과 미리보기

`글꼴·색상·크기 설정 + 미리보기` 노드에서 다음 항목을 한 번에 설정합니다.

- 본문/댓글 글꼴과 크기
- 이미지 너비, 여백, 줄 간격
- 본문, 밑줄, 형광펜, 배경 색상
- 설치된 맑은 고딕·굴림·바탕·Noto Sans/Serif KR 선택 또는 직접 글꼴 경로 입력

각 색상 아래의 `색상표 열기` 버튼으로 색을 선택할 수 있습니다. 두 번째 출력인 `스타일_미리보기`가 실제 글꼴·크기·색상 예시를 보여 줍니다. 색연필 밑줄의 기본색은 붉은색 `#C63B3B`입니다.

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
