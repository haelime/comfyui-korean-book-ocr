# ComfyUI 한국어 책 OCR

책 사진을 한국어로 OCR하고, Qwen으로 오타와 맞춤법을 교정한 뒤 문장 이미지로 저장하는 ComfyUI 워크플로우입니다.

작업 방식은 두 가지입니다.

- 사진마다 필요한 부분을 마스킹해 한 장씩 처리
- 사진 폴더 전체를 TXT로 만든 뒤 한꺼번에 이미지로 변환

## 1. ComfyUI 설치

이미 ComfyUI를 사용하고 있다면 이 단계는 건너뛰세요.

### Comfy Desktop 설치 — 권장

1. [Comfy Desktop 공식 Windows 설치 안내](https://docs.comfy.org/installation/desktop/windows)에서 설치 파일을 받습니다.
2. 받은 `.exe`를 실행합니다.
3. Comfy Desktop을 열고 첫 번째 ComfyUI 설치본을 만듭니다.
4. ComfyUI 화면이 정상적으로 열리는지 확인한 뒤 완전히 종료합니다.

Comfy Desktop은 Windows 10 이상을 지원하며, 전용 GPU 사용이 권장됩니다. 설치 위치는 사용자가 바꿀 수 있습니다.

### Windows portable 설치 — 선택

Desktop 대신 압축판을 사용하려면 [ComfyUI portable 공식 안내](https://docs.comfy.org/installation/comfyui_portable_windows)를 따르세요.

1. 그래픽카드에 맞는 압축 파일을 받습니다.
2. 7-Zip 등으로 압축을 풉니다.
3. NVIDIA 버전은 `run_nvidia_gpu.bat`을 더블클릭해 실행합니다.

## 2. ComfyUI 폴더 찾기

커스텀 노드는 반드시 현재 사용하는 ComfyUI의 `custom_nodes` 폴더 안에 넣어야 합니다.

### Comfy Desktop의 일반적인 위치

파일 탐색기 주소창에 다음 경로를 붙여넣습니다.

```text
%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Installs
```

설치 이름의 폴더를 차례로 열어 다음 구조를 찾습니다.

```text
ComfyUI-Installs/
└─ 설치_이름/
   └─ ComfyUI/
      ├─ custom_nodes/   ← 여기에 설치
      ├─ models/
      └─ user/
```

일부 이전 Desktop 설치는 다음 위치를 사용합니다.

```text
%USERPROFILE%\ComfyUI-Installs
```

Comfy Desktop의 사진·결과 파일은 설치본과 별도로 다음 공유 폴더에 저장될 수 있습니다.

```text
%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Shared\input
%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Shared\output
```

`Program Files` 안의 Comfy Desktop 프로그램 파일이나 `resource/ComfyUI`에는 커스텀 노드를 넣지 마세요.

### Windows portable의 위치

압축을 푼 장소에 따라 앞부분은 달라지지만 내부 구조는 다음과 같습니다.

```text
ComfyUI_windows_portable/
├─ ComfyUI/
│  └─ custom_nodes/      ← 여기에 설치
├─ python_embeded/
└─ run_nvidia_gpu.bat
```

예를 들어 바탕 화면에 압축을 풀었다면 다음과 비슷합니다.

```text
C:\Users\사용자이름\Desktop\ComfyUI_windows_portable\ComfyUI\custom_nodes
```

## 3. 한국어 책 OCR 설치

1. ComfyUI를 완전히 종료합니다.
2. 이 GitHub 페이지 위쪽의 **Code → Download ZIP**을 누릅니다.
3. ZIP 압축을 풉니다.
4. 압축을 푼 폴더 전체를 앞에서 찾은 `custom_nodes` 안에 넣습니다.
5. 폴더 안의 `install_windows.bat`을 더블클릭합니다.
6. **설치가 끝났습니다**라는 문구가 나오면 ComfyUI를 다시 실행합니다.
7. 워크플로우 메뉴에서 `korean_ocr_to_image`를 엽니다.

최종 구조는 다음과 같아야 합니다. 같은 이름의 폴더가 이중으로 들어가면 안 됩니다.

```text
ComfyUI/
└─ custom_nodes/
   └─ comfyui-korean-book-ocr-main/
      ├─ __init__.py
      ├─ install_windows.bat
      └─ requirements.txt
```

맞춤법 자동 교정을 사용하려면 [Ollama](https://ollama.com/download/windows)를 설치합니다. 설치 후 `install_windows.bat`을 다시 실행하면 Qwen 모델 다운로드 여부를 묻습니다.

더 자세한 내용: [Windows 설치 가이드](docs/INSTALL.ko.md)

## 권장 작업 폴더

책이나 작업 단위마다 다음과 같이 폴더를 만들어 두는 것을 권장합니다.

```text
책_이름/
├─ image/    원본 책 사진
├─ text/     OCR 후 직접 수정할 TXT
└─ output/   완성된 문장 이미지
```

파일 이름은 서로 같게 유지하면 찾기 쉽습니다.

```text
image/001.jpg → text/001.txt → output/001.png
image/002.jpg → text/002.txt → output/002.png
```

## 방법 1: 사진마다 마스킹해서 작업

한 사진에서 특정 문장이나 문단만 골라 OCR할 때 사용합니다. 워크플로우 위쪽 영역을 이용합니다.

1. `image` 폴더에 원본 사진을 정리합니다.
2. `Load Image`에서 처리할 사진 한 장을 불러옵니다.
3. 노드를 우클릭하고 `Open in Mask Editor`를 엽니다.
4. OCR할 부분만 흰색으로 칠하고 저장합니다.
5. Queue를 실행해 OCR과 맞춤법 교정을 진행합니다.
6. `OCR 텍스트 수정 → 이미지`에서 글자를 직접 확인하고 수정합니다.
7. 필요한 꾸밈 문법을 넣고 다시 Queue를 실행합니다.
8. 완성 이미지를 `output` 폴더에 원본과 같은 이름으로 정리합니다.

마스크를 칠하지 않으면 사진 전체를 OCR합니다. 교정문을 따로 보관하려면 편집한 내용을 같은 이름의 TXT로 `text` 폴더에 저장하세요.

## 방법 2: 폴더 전체를 대량 작업

사진을 모두 OCR한 뒤 TXT를 차례로 검토하고, 파일마다 이미지 한 장을 만들 때 사용합니다. 워크플로우 아래쪽의 ①·② 노드를 이용합니다.

### 1단계: 사진 폴더를 TXT로 변환

1. 왼쪽 `① 사진 폴더 → OCR 텍스트 파일` 노드만 `실행`을 켭니다.
2. 오른쪽 `② 텍스트 폴더 → 파일별 이미지` 노드의 `실행`은 끕니다.
3. `사진 폴더 선택…`에서 `image` 폴더를 선택합니다.
4. `텍스트 저장 폴더 선택…`에서 `text` 폴더를 선택합니다.
5. Queue를 실행합니다.

사진마다 같은 이름의 TXT가 생성됩니다. 하위 폴더도 같은 구조로 유지됩니다.

### 중간 작업: TXT 수정

`text` 폴더의 TXT를 메모장이나 원하는 편집기로 열어 다음 내용을 확인합니다.

- OCR 오타와 맞춤법
- 문단과 줄바꿈
- 밑줄·굵게·이탤릭·형광펜·댓글 문법

`기존_텍스트_보호`가 켜져 있으면 수정한 TXT를 다시 OCR해 덮어쓰지 않습니다.

### 2단계: TXT마다 이미지 한 장 생성

1. 왼쪽 ① 노드의 `실행`을 끕니다.
2. 오른쪽 ② 노드의 `실행`만 켭니다.
3. 위쪽 `글꼴·색상·크기 설정 + 미리보기`에서 디자인을 정합니다.
4. `이미지 저장 폴더 선택…`에서 `output` 폴더를 선택합니다.
5. Queue를 실행합니다.

①의 `텍스트_폴더` 출력이 ②에 연결되어 있으므로 TXT 폴더를 다시 선택할 필요가 없습니다. TXT 파일 하나마다 같은 이름의 PNG가 생성됩니다.

## 꾸밈 문법

```markdown
__붉은 색연필 밑줄__[^1]
**굵게**
*이탤릭*
~~형광펜~~

[^1]: 밑줄에 연결할 작은 붉은 댓글
```

꾸밈은 여러 줄에 걸쳐 사용할 수 있지만 서로 중첩하지 마세요. 붉은 밑줄에는 색연필의 압력 변화와 안료 입자 질감이 적용됩니다.

자세한 사용법: [워크플로우 안내](docs/WORKFLOW.ko.md)

## 문제가 생기면

- 노드가 보이지 않음: ComfyUI를 완전히 종료했다가 다시 실행합니다.
- 폴더 선택창이 열리지 않음: ComfyUI를 재시작하고 `Ctrl+F5`를 누릅니다.
- 입력 타입 오류: 열린 탭을 닫고 최신 `korean_ocr_to_image`를 다시 엽니다.
- Ollama 연결 오류: Ollama를 실행하거나 `자동_교정`을 끕니다.

더 많은 해결 방법: [설치 가이드의 문제 해결](docs/INSTALL.ko.md#자주-발생하는-문제)

## 라이선스

MIT
