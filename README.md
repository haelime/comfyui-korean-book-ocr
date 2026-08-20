# ComfyUI 한국어 책 OCR

소설책 사진에서 원하는 부분을 한국어로 OCR하고, 로컬 Qwen으로 오타와 맞춤법을 교정한 뒤 문장 이미지로 저장하는 ComfyUI 커스텀 노드입니다.

- 마스크로 칠한 부분만 OCR
- 마스크가 없으면 사진 전체를 OCR
- Qwen은 오타와 맞춤법만 교정하며 꾸밈은 추천하지 않음
- 텍스트를 직접 수정한 뒤 글꼴, 색상, 밑줄, 형광펜 등을 적용

## 설치

1. ComfyUI를 완전히 종료합니다.
2. 위쪽의 **Code → Download ZIP**으로 파일을 받습니다.
3. 압축을 푼 폴더를 `ComfyUI/custom_nodes/` 안에 넣습니다.
4. 폴더 안의 `install_windows.bat`을 더블클릭합니다.
5. 설치가 끝나면 ComfyUI를 다시 실행합니다.
6. 워크플로우 메뉴에서 `korean_ocr_to_image`를 엽니다.

오타·맞춤법 자동 교정을 사용하려면 [Ollama](https://ollama.com/download/windows)를 설치해야 합니다. 설치 후 `install_windows.bat`을 다시 실행하면 `qwen3:8b` 모델을 받을 수 있습니다. AI 교정이 필요 없으면 노드의 `자동_교정`을 끄세요.

자세한 내용: [Windows 설치 가이드](docs/INSTALL.ko.md)

## 여러 사진 한꺼번에 처리

1. `ComfyUI/input/대량_OCR_사진`에 사진을 넣습니다.
2. 기존 `korean_ocr_to_image` 워크플로우 아래쪽에서 `사진 폴더 선택…` 버튼으로 폴더를 지정한 뒤 ① 단계를 실행합니다.
3. `ComfyUI/output/korean_book_ocr/text`의 TXT를 직접 수정합니다.
4. ② 단계를 실행하면 TXT마다 PNG 한 장이 `output/korean_book_ocr/images`에 저장됩니다.

기존 TXT는 기본적으로 덮어쓰지 않으므로 수정 내용이 보호됩니다.

## 사용법

1. `Load Image`에서 책 사진을 선택합니다.
2. 일부만 OCR하려면 노드를 우클릭하고 `Open in Mask Editor`에서 원하는 부분을 흰색으로 칠합니다.
3. Queue를 실행해 OCR과 맞춤법 교정을 진행합니다.
4. `OCR 텍스트 수정 → 이미지`에서 내용을 직접 수정합니다.
5. 필요한 꾸밈 문법을 넣고 다시 Queue를 실행해 저장합니다.

## 꾸밈 문법

```markdown
__붉은 색연필 밑줄__[^1]
**굵게**
*이탤릭*
~~형광펜~~

[^1]: 밑줄에 연결할 작은 붉은 댓글
```

꾸밈은 여러 줄에 걸쳐 사용할 수 있지만 서로 중첩하지 마세요.

자세한 내용: [워크플로우 사용법](docs/WORKFLOW.ko.md)

## 문제가 생기면

- 노드가 보이지 않음: ComfyUI를 완전히 종료했다가 다시 실행합니다.
- `No module named paddleocr`: `install_windows.bat`을 다시 실행합니다.
- Ollama 연결 오류: Ollama를 실행하거나 `자동_교정`을 끕니다.
- 입력 타입 오류: 최신 `korean_ocr_to_image.workflow.json`을 다시 엽니다.

더 많은 해결 방법은 [설치 가이드의 문제 해결](docs/INSTALL.ko.md#자주-발생하는-문제)을 확인하세요.

## 기타 문서

- [상세 기능 설명](README.ko.md)
- [함께 쓰기 좋은 유틸리티 노드](UTILITY_NODES.md)

## 라이선스

MIT
