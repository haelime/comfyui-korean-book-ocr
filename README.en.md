# ComfyUI Korean Book OCR

[한국어](README.md) | [English](README.en.md)

OCR photographed Korean book pages, correct OCR errors and Korean spelling with local Qwen, edit the text, and render it as styled quote images in ComfyUI.

Two workflows are available in the same `korean_ocr_to_image` workspace:

- Process one photo at a time with a painted mask.
- Convert an entire image folder to TXT files, review them, then render one PNG per TXT file.

<details>
<summary>Example: source image → OCR text → rendered image</summary>

#### 1. Source image

![Example photo for Korean book OCR](examples/wakamo.jpg)

#### 2. Extracted text

```text
장르: 소셜 채널
P
와카모는
책을 먹었어요
```

[Open the text file](examples/wakamo.txt)

#### 3. Rendered result

![Rendered OCR text](examples/wakamo.png)

</details>

## 1. Install ComfyUI

Skip this section if ComfyUI is already installed.

### Comfy Desktop — recommended

1. Download the installer from the [official Comfy Desktop Windows guide](https://docs.comfy.org/installation/desktop/windows).
2. Run the downloaded `.exe`.
3. Open Comfy Desktop and create your first ComfyUI installation.
4. Confirm that the ComfyUI interface opens, then close it completely.

Comfy Desktop supports Windows 10 or later. A dedicated GPU is recommended, and the installation location can be changed during setup.

### Windows portable — optional

Follow the [official ComfyUI portable guide](https://docs.comfy.org/installation/comfyui_portable_windows) if you prefer the extracted portable package.

1. Download the package for your GPU.
2. Extract it with 7-Zip or a similar tool.
3. For the NVIDIA build, double-click `run_nvidia_gpu.bat`.

## 2. Find the ComfyUI folder

This custom node must be placed inside the `custom_nodes` directory of the ComfyUI installation you actually use.

### Typical Comfy Desktop location

Paste this path into the File Explorer address bar:

```text
%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Installs
```

Open your installation folder and find this structure:

```text
ComfyUI-Installs/
└─ installation_name/
   └─ ComfyUI/
      ├─ custom_nodes/   ← install here
      ├─ models/
      └─ user/
```

Some older Desktop installations use:

```text
%USERPROFILE%\ComfyUI-Installs
```

Desktop may keep input and output data in a separate shared directory:

```text
%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Shared\input
%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Shared\output
```

Do not install the node into Comfy Desktop program files under `Program Files` or into `resource/ComfyUI`.

### Windows portable location

The outer extraction path varies, but the internal structure is normally:

```text
ComfyUI_windows_portable/
├─ ComfyUI/
│  └─ custom_nodes/      ← install here
├─ python_embeded/
└─ run_nvidia_gpu.bat
```

## 3. Install Korean Book OCR

1. Close ComfyUI completely.
2. On this GitHub page, select **Code → Download ZIP**.
3. Extract the ZIP.
4. Move the entire extracted folder into the `custom_nodes` directory found above.
5. Double-click `install_windows.bat` inside the folder.
6. Wait for the **installation complete** message, then restart ComfyUI.
7. Open `korean_ocr_to_image` from the workflow menu.

The final directory must look like this. Do not leave an extra duplicate folder level.

```text
ComfyUI/
└─ custom_nodes/
   └─ comfyui-korean-book-ocr-main/
      ├─ __init__.py
      ├─ install_windows.bat
      └─ requirements.txt
```

Install [Ollama](https://ollama.com/download/windows) to use automatic Korean spelling correction. Run `install_windows.bat` again after installing Ollama; it will offer to download the Qwen model.

## Recommended project folders

Create one project directory per book or job:

```text
book_name/
├─ image/    original page photos
├─ text/     OCR text to review
└─ output/   final rendered images
```

Keep matching base names so every stage is easy to track:

```text
image/001.jpg → text/001.txt → output/001.png
image/002.jpg → text/002.txt → output/002.png
```

## Method 1: Mask and process one photo at a time

Use the upper section of the workflow when you need OCR from a specific sentence or paragraph.

1. Organize the original photos in `image`.
2. Load one photo with `Load Image`.
3. Right-click the node and select `Open in Mask Editor`.
4. Paint only the OCR area in white and save the mask.
5. Queue the workflow to run OCR and spelling correction.
6. Review and edit the text in `OCR 텍스트 수정 → 이미지`.
7. Add optional style markup and queue again.
8. Organize the final image in `output` with the same base name as the photo.

If the mask is empty, the entire photo is used. To preserve the edited text separately, save it as a same-named TXT file in `text`.

## Method 2: Process an entire folder

Use batch nodes ① and ② in the lower section of the same workflow.

### Stage 1: Image folder to TXT files

1. Turn on `실행` only in the left node, `① 사진 폴더 → OCR 텍스트 파일`.
2. Keep `실행` off in the right node, `② 텍스트 폴더 → 파일별 이미지`.
3. Select `image` with `사진 폴더 선택…`.
4. Select `text` with `텍스트 저장 폴더 선택…`.
5. Queue the workflow.

Each image produces a same-named TXT file. Nested folders are preserved.

### Review the TXT files

Open the files in `text` with any editor and check:

- OCR and spelling errors
- Paragraphs and line breaks
- Underline, bold, italic, highlighter, and comment markup

Keep `기존_텍스트_보호` enabled so reviewed TXT files are not overwritten by another OCR run.

### Stage 2: One image per TXT file

1. Turn off `실행` in the left node ①.
2. Turn on `실행` only in the right node ②.
3. Choose the design in `글꼴·색상·크기 설정 + 미리보기`.
4. Select `output` with `이미지 저장 폴더 선택…`.
5. Queue the workflow.

The `텍스트_폴더` output of node ① is connected to node ②, so the TXT folder does not need to be selected again. One same-named PNG is generated per TXT file.

## Style markup

```markdown
__red colored-pencil underline__[^1]
**bold**
*italic*
~~highlighter~~

[^1]: a small red comment attached to the underline
```

Markers can span multiple lines, but do not nest them. The red underline includes irregular pressure, paper gaps, and pigment-grain texture.

## Reviewing a TXT folder with Claude or Codex

The following prompts are examples for an AI tool that can read and write files in a folder. Keep the original `text` directory and save reviewed files into a new directory such as `text_reviewed`.

```text
book_name/
├─ image/
├─ text/
├─ text_reviewed/
└─ output/
```

After review, set node ①'s TXT output folder to `text_reviewed` while leaving ① disabled. The connected path will be passed to node ②.

<details>
<summary>Example 1: Correct OCR and Korean spelling in every TXT file</summary>

```text
Read every .txt file recursively from the specified text directory as UTF-8.
Review each file independently and save it under text_reviewed while preserving
the same relative path and file name. Never overwrite a source file.

Rules:
1. Correct only clear OCR substitutions, missing or duplicated syllables,
   incorrect final consonants, spacing, punctuation, and quotation marks.
2. Infer obscured characters from context only when confidence is high.
3. Preserve the author's style, dialect, archaic wording, proper nouns,
   and intentional nonstandard grammar.
4. Preserve paragraphs and line breaks. Do not add, summarize, or translate content.
5. Preserve existing __underline__, **bold**, *italic*, ~~highlight~~,
   and [^footnote] markup without moving it.
6. Do not silently change uncertain passages. Record the file name, passage,
   candidates, and reasoning in a separate review_report.md.

Report the number of processed, changed, and uncertain files when finished.
```

</details>

<details>
<summary>Example 2: Infer emphasis and insert style markup only</summary>

The built-in Qwen correction node does not recommend decoration. Use this optional prompt only after spelling review.

```text
Read every .txt file in text_reviewed. Do not alter a single body-text character.
Insert only the supported markup below and save the results under text_styled,
preserving every file name and relative directory.

Supported markup:
- __phrase__ : red colored-pencil underline
- **phrase** : bold
- *phrase* : italic
- ~~phrase~~ : highlighter
- __phrase__[^1] with [^1]: comment : small red comment attached to an underline

Emphasis rules:
1. Select sentences that compress the scene's theme or central meaning.
2. Select emotional turns and important character decisions.
3. Select memorable imagery, metaphors, reversals, or recurring expressions.
4. Use italic sparingly for inner thought.
5. Decorate only about 5–12% of each file.
6. Select complete meaningful phrases; never split a word or isolate a particle.
7. Do not nest markup, and close every marker.
8. One marker pair may span multiple lines.
9. Footnote comments must be one short reaction or question. Do not invent analysis.

After removing markup and footnote definitions, the body text and line breaks
must be exactly identical to the source. If this cannot be guaranteed,
leave that file undecorated.
```

</details>

<details>
<summary>Example 3: Compare page photos and optionally verify the published source</summary>

For best accuracy, pair same-named files such as `image/001.jpg` and `text/001.txt`. Source searching requires Claude, Codex, or another tool with web access; the local Qwen node does not browse the internet.

```text
Pair each photo in image with the same-named TXT file in text.
Save reviewed files under text_reviewed with the same directory structure.
Never overwrite the originals.

Review order:
1. Treat characters visibly present in the photo as the primary evidence.
2. Infer possible characters from grammar and surrounding context when blurred.
3. Apply an inference only when there is one clear, high-confidence candidate.
4. If multiple candidates remain, preserve the OCR text and record the candidates
   and reasoning in review_report.md.
5. When title, author, translator, publisher, and edition details are available,
   search legal and reliable sources such as publisher pages, library records,
   or official previews to cross-check the passage.
6. Do not use a search result from a different edition or translation as evidence.
7. Never add text merely because a similar sentence appears in search results.
8. Preserve style, dialect, archaic language, proper nouns, and paragraph structure.

For every change, record:
- file name
- OCR sentence
- corrected sentence
- evidence: photo / contextual inference / verified source
- confidence: high / medium / low
- source URL and edition details, only when a web source was used

Do not reproduce long copyrighted passages in the report. Record only the short
fragment and location information needed to explain the correction.
```

</details>

## Troubleshooting

- Nodes are missing: close ComfyUI completely and restart it.
- Folder picker does not open: restart ComfyUI and press `Ctrl+F5`.
- Input type error: close the old workflow tab and reopen the latest `korean_ocr_to_image` workflow.
- Ollama connection error: start Ollama or disable `자동_교정`.

See the [Korean installation guide](docs/INSTALL.ko.md) for additional troubleshooting.

## License

MIT
