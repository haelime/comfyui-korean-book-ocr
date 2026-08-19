# 함께 쓰기 좋은 ComfyUI 유틸리티 노드

이 저장소의 예제 워크플로에는 필요하지 않습니다. 더 큰 책 OCR·문장 카드 제작 파이프라인을 구성할 때 선택적으로 설치하세요.

## 1. ComfyUI-KJNodes

<https://github.com/kijai/ComfyUI-KJNodes>

- 이미지/마스크 리사이즈, 마스크 미리보기, 색상→마스크, 이미지 연결에 유용합니다.
- 여러 인용문 이미지를 세로로 연결하거나 OCR 전에 페이지 크기를 통일할 때 특히 편합니다.
- `Create Text Mask`로 별도 텍스트 마스크를 만들 수도 있습니다.

## 2. ComfyUI-Custom-Scripts (pythongosssss)

<https://github.com/pythongosssss/ComfyUI-Custom-Scripts>

- `Show Text`로 OCR 문자열을 중간 확인할 수 있습니다.
- `String Function`으로 반복 오인식 치환, 접두/접미 문구 추가에 유용합니다.
- 시스템 알림과 UI 개선 기능도 제공해 대량 페이지 처리 완료를 확인하기 좋습니다.

## 3. ComfyUI_Comfyroll_CustomNodes

<https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes>

- 문자열 분리·연결·치환·블랙리스트·길이 계산과 텍스트 파일 저장 노드가 있습니다.
- 여러 OCR 페이지를 파일로 축적하거나 조건에 따라 텍스트 경로를 전환할 때 유용합니다.

## 4. ComfyUI_LayerStyle

<https://github.com/chflame163/ComfyUI_LayerStyle>

- Photoshop 방식의 이미지/마스크 합성, 블렌드, 그림자, 텍스트 이미지 기능을 제공합니다.
- 배경 종이 질감, 스티커, 테두리, 추가 주석 레이어를 조합할 때 적합합니다.

## 5. rgthree-comfy

<https://github.com/rgthree/rgthree-comfy>

- 그룹별 mute/bypass, 선택한 출력만 Queue, 링크 검사·복구 기능으로 큰 워크플로를 관리하기 편해집니다.
- OCR, 텍스트 수정, 렌더링, 저장 단계를 그룹으로 나누어 부분 실행할 때 유용합니다.

## 6. ComfyUI-Impact-Pack

<https://github.com/ltdrdata/ComfyUI-Impact-Pack>

- `MaskPainter`, 이진 마스크 변환, 마스크 배치/리스트 변환과 조건 분기 유틸리티를 제공합니다.
- 여러 마스크 영역이나 페이지 배치를 자동 처리하는 고급 워크플로에 어울립니다.

## 추천 조합

- **가볍게:** 이 저장소 + ComfyUI-Custom-Scripts
- **페이지 편집:** 위 조합 + KJNodes + LayerStyle
- **대량 자동화:** 위 조합 + Comfyroll + Impact Pack
- **복잡한 그래프 관리:** 어느 조합이든 rgthree-comfy 추가

