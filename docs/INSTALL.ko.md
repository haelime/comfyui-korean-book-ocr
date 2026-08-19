# Windows 초보자 설치 가이드

이 문서는 개발 도구를 몰라도 `한국어 책 OCR → Qwen 오타·맞춤법 교정 → 텍스트 수정 → 이미지 저장` 워크플로우를 설치할 수 있도록 설명합니다.

## 먼저 알아둘 점

- `uv`, Git, 별도의 Python은 필요하지 않습니다.
- ComfyUI Desktop 또는 Windows portable이 먼저 설치되어 있어야 합니다.
- Qwen 교정은 선택 기능입니다. Ollama가 없어도 OCR, 직접 수정, 이미지 만들기는 사용할 수 있습니다.
- 첫 OCR 실행에서는 한국어 모델을 내려받으므로 인터넷 연결과 시간이 필요합니다.

## 1. 파일 받기

1. GitHub 저장소 위쪽의 초록색 **Code** 버튼을 누릅니다.
2. **Download ZIP**을 누릅니다.
3. 받은 ZIP 파일을 우클릭하고 **압축 풀기**를 선택합니다.
4. 압축을 푼 폴더 이름 끝에 `-main`이 붙어 있어도 괜찮습니다.

## 2. ComfyUI의 custom_nodes 폴더에 넣기

ComfyUI를 완전히 종료한 다음, 압축을 푼 폴더 전체를 `custom_nodes` 안으로 옮깁니다.

정상적인 구조는 다음과 같습니다.

```text
ComfyUI/
└─ custom_nodes/
   └─ comfyui-korean-book-ocr-main/
      ├─ __init__.py
      ├─ install_windows.bat
      └─ requirements.txt
```

`comfyui-korean-book-ocr-main` 폴더 안에 같은 이름의 폴더가 한 번 더 들어 있으면 바깥 폴더를 제거해 위 구조로 맞추세요.

## 3. 더블클릭 설치

1. `install_windows.bat`을 더블클릭합니다.
2. 검은 창에서 OCR 패키지 설치가 끝날 때까지 기다립니다.
3. Ollama가 설치되어 있고 `qwen3:8b`가 없다면 다운로드 여부를 묻습니다. 사용할 경우 `Y` 또는 Enter를 누릅니다. 모델은 약 5.2GB입니다.
4. **설치가 끝났습니다**라는 문구가 나오면 아무 키나 눌러 창을 닫습니다.

이 설치 파일은 다음 작업을 자동으로 합니다.

- Desktop의 `.venv` 또는 portable의 `python_embeded` 탐색
- ComfyUI가 실제 사용하는 Python에 PaddleOCR 설치
- `user/default/workflows`에 단일 작업과 대량 작업 워크플로우 복사
- 설치된 Ollama와 Qwen 모델 확인

## 4. Qwen 오타·맞춤법 교정 사용하기

AI 교정이 필요하면 [Ollama Windows 설치 페이지](https://ollama.com/download/windows)에서 Ollama를 설치하고 실행하세요. 그다음 `install_windows.bat`을 다시 실행하면 Qwen 모델을 받을 수 있습니다.

AI 교정이 필요 없으면 워크플로우에서 `자동_교정`을 끄세요. Qwen은 꾸밈을 추천하거나 본문에 꾸밈 기호를 넣지 않고, 오타와 맞춤법만 두 차례 검토합니다.

## 5. ComfyUI에서 열기

1. ComfyUI를 완전히 종료했다가 다시 실행합니다.
2. 한 장씩 작업하려면 `korean_ocr_to_image`, 폴더 단위로 작업하려면 `korean_ocr_batch`를 엽니다.
3. 메뉴에 없다면 저장소의 `korean_ocr_to_image.workflow.json`을 화면으로 끌어다 놓습니다.
4. 아래 노드가 보이면 설치가 완료된 것입니다.
   - `마스크 영역 한국어 OCR`
   - `로컬 AI OCR 오타·맞춤법 교정`
   - `글꼴·색상·크기 설정 + 미리보기`
   - `OCR 텍스트 수정 → 이미지`

## 업데이트

새 ZIP을 받아 기존 커스텀 노드 폴더의 파일을 덮어쓴 뒤 `install_windows.bat`을 다시 실행하고 ComfyUI를 재시작하세요.

## 자주 발생하는 문제

### `ComfyUI 전용 Python을 찾지 못했습니다`

저장소 폴더가 실제 ComfyUI의 `custom_nodes` 안에 있는지 확인하세요. Desktop과 portable을 둘 다 설치했다면 현재 실행하는 ComfyUI 쪽에 넣어야 합니다.

### `No module named paddleocr`

ComfyUI를 종료하고 `install_windows.bat`을 다시 실행하세요. 설치 도중 빨간 오류가 있었다면 창의 마지막 오류 내용을 확인하세요.

### Ollama에 연결할 수 없음

Ollama 앱을 실행하세요. 계속 안 되면 브라우저에서 `http://127.0.0.1:11434`가 열리는지 확인합니다. AI 없이 진행하려면 `자동_교정`을 끕니다.

### 노드가 빨간색이거나 입력 타입 오류가 남음

ComfyUI를 완전히 재시작하고 저장소의 최신 `korean_ocr_to_image.workflow.json`을 다시 여세요. 이전 버전의 열린 탭은 새 노드 입출력 구조를 유지하지 못할 수 있습니다.

### 한국어 글꼴이 네모로 표시됨

스타일 설정 노드에서 `맑은 고딕`, `굴림`, `바탕`, `Noto Sans KR`, `Noto Serif KR` 중 하나를 고르거나 한글을 지원하는 TTF/TTC 경로를 직접 지정하세요.

## 개발자를 위한 수동 설치(선택)

자동 설치를 쓰지 않을 때만 ComfyUI의 Python으로 다음 명령을 실행합니다. `uv` 대신 기본 `pip` 명령이면 충분합니다.

```powershell
& "C:\경로\ComfyUI\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

portable은 `.venv\Scripts\python.exe` 대신 상위 폴더의 `python_embeded\python.exe`를 사용합니다.
