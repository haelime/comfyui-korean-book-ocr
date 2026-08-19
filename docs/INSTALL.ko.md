# Windows 설치 가이드

이 문서는 ComfyUI를 처음 사용하는 사람도 `한국어 책 OCR → 로컬 AI 교정 → 꾸민 이미지` 워크플로우를 설치할 수 있도록 순서대로 설명합니다.

## 1. 준비물

- Windows 10 이상
- 설치되어 실행되는 ComfyUI Desktop 또는 portable
- Git
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Ollama](https://ollama.com/download/windows)

Git과 uv가 없다면 PowerShell에서 설치합니다.

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
winget install --id Ollama.Ollama -e
```

설치 후 PowerShell을 새로 열어 `git --version`, `uv --version`, `ollama --version`이 출력되는지 확인합니다.

## 2. ComfyUI 폴더 찾기

아래 이름이 보이는 폴더가 ComfyUI 루트입니다.

```text
ComfyUI/
├─ custom_nodes/
├─ user/
└─ .venv/               # Desktop 설치에서 주로 사용
```

portable 버전은 보통 상위 폴더에 `python_embeded/`가 있습니다.

## 3. 커스텀 노드 내려받기

ComfyUI를 완전히 종료한 후 PowerShell에서 실제 경로로 바꿔 실행합니다.

```powershell
cd "C:\경로\ComfyUI\custom_nodes"
git clone https://github.com/haelime/comfyui-korean-book-ocr.git
cd comfyui-korean-book-ocr
```

ZIP으로 받았다면 압축을 풀어 최종 구조가 다음과 같은지 확인합니다. 폴더가 이중으로 겹치면 안 됩니다.

```text
custom_nodes/comfyui-korean-book-ocr/__init__.py
```

## 4. Python 패키지 설치

ComfyUI Desktop의 `.venv`를 사용하는 경우:

```powershell
uv pip install --python "C:\경로\ComfyUI\.venv\Scripts\python.exe" -r requirements.txt
```

Windows portable을 사용하는 경우:

```powershell
uv pip install --python "C:\경로\ComfyUI_windows_portable\python_embeded\python.exe" -r requirements.txt
```

중요: 일반 Windows Python이 아니라 **ComfyUI가 실제로 사용하는 Python**에 설치해야 합니다.

## 5. 로컬 AI 모델 설치

Ollama를 실행한 뒤 PowerShell에서 다음 명령을 실행합니다. 모델 크기는 약 5.2GB입니다.

```powershell
ollama pull qwen3:8b
ollama list
```

목록에 `qwen3:8b`가 표시되면 준비가 끝났습니다. 교정은 기본적으로 `http://127.0.0.1:11434`의 로컬 Ollama에만 요청됩니다.

## 6. 워크플로우 설치

저장소의 `korean_ocr_to_image.workflow.json` 파일을 ComfyUI 화면에 직접 끌어다 놓아도 됩니다.

워크플로우 메뉴에 계속 표시하려면 다음 위치로 복사합니다.

```powershell
Copy-Item .\korean_ocr_to_image.workflow.json "C:\경로\ComfyUI\user\default\workflows\korean_ocr_to_image.json" -Force
```

## 7. 첫 실행 확인

1. ComfyUI를 완전히 다시 시작합니다.
2. `korean_ocr_to_image` 워크플로우를 엽니다.
3. 아래 노드들이 보이는지 확인합니다.
   - `마스크 영역 한국어 OCR`
   - `로컬 AI OCR 교정 + 꾸밈 추천`
   - `글꼴·색상·크기 설정 + 미리보기`
   - `OCR 텍스트 수정 → 이미지`
4. `Load Image`에서 책 사진을 선택하고 마스크를 칠한 뒤 Queue를 실행합니다.

첫 OCR 실행에서는 PaddleOCR 모델을 내려받기 때문에 평소보다 오래 걸릴 수 있습니다. Qwen도 처음 호출할 때 GPU 메모리에 적재되어 시간이 더 걸립니다.

## 업데이트

```powershell
cd "C:\경로\ComfyUI\custom_nodes\comfyui-korean-book-ocr"
git pull
uv pip install --python "C:\경로\ComfyUI\.venv\Scripts\python.exe" -r requirements.txt
Copy-Item .\korean_ocr_to_image.workflow.json "C:\경로\ComfyUI\user\default\workflows\korean_ocr_to_image.json" -Force
```

그다음 ComfyUI를 재시작하고 업데이트된 워크플로우를 다시 엽니다.

## 자주 발생하는 문제

### `No module named paddleocr`

패키지가 다른 Python에 설치된 상태입니다. 4단계에서 ComfyUI의 `.venv` 또는 `python_embeded` 경로를 다시 지정하세요.

### Ollama에 연결할 수 없음

Ollama 앱을 실행하고 아래 주소가 열리는지 확인합니다.

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

### 노드가 빨간색이거나 입력 타입 오류가 남음

ComfyUI를 완전히 종료했다가 다시 실행하고, 화면에 남아 있던 이전 워크플로우 대신 저장소의 최신 JSON을 다시 여세요.

### 한국어 글꼴이 네모로 표시됨

스타일 설정 노드에서 `맑은 고딕`, `굴림`, `바탕`, `Noto Sans KR`, `Noto Serif KR` 중 하나를 선택하거나 한글 지원 TTF/TTC 경로를 직접 입력하세요.

