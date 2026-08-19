import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

function showFolderDialog(title, folders, currentValue) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.style.cssText = "min-width:440px;max-width:80vw;padding:22px;border:1px solid #666;border-radius:10px;background:#242424;color:#eee;";

    const heading = document.createElement("h3");
    heading.textContent = title;
    heading.style.marginTop = "0";

    const help = document.createElement("p");
    help.textContent = "목록에서 고르거나 새 폴더 이름을 입력하세요.";

    const listId = `korean-folder-${Date.now()}`;
    const input = document.createElement("input");
    input.type = "text";
    input.value = currentValue || "";
    input.setAttribute("list", listId);
    input.style.cssText = "box-sizing:border-box;width:100%;padding:9px;background:#171717;color:#fff;border:1px solid #777;border-radius:5px;";

    const dataList = document.createElement("datalist");
    dataList.id = listId;
    for (const folder of folders) {
      const option = document.createElement("option");
      option.value = folder;
      dataList.appendChild(option);
    }

    const buttons = document.createElement("div");
    buttons.style.cssText = "display:flex;justify-content:flex-end;gap:8px;margin-top:18px;";
    const cancel = document.createElement("button");
    cancel.textContent = "취소";
    const choose = document.createElement("button");
    choose.textContent = "이 폴더 사용";
    buttons.append(cancel, choose);

    const finish = (value) => {
      dialog.close();
      dialog.remove();
      resolve(value);
    };
    cancel.addEventListener("click", () => finish(null));
    choose.addEventListener("click", () => {
      const value = input.value.trim().replaceAll("\\", "/").replace(/^\/+|\/+$/g, "");
      if (value) finish(value);
    });
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish(null);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        choose.click();
      }
    });

    dialog.append(heading, help, input, dataList, buttons);
    document.body.appendChild(dialog);
    dialog.showModal();
    input.focus();
  });
}

async function pickComfyFolder(node, widgetName, kind, title) {
  const widget = node.widgets?.find((item) => item.name === widgetName);
  if (!widget) return;
  try {
    const response = await api.fetchApi(`/korean-book-ocr/folders?kind=${kind}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const value = await showFolderDialog(title, data.folders || [], widget.value);
    if (value) {
      widget.value = value;
      app.graph.setDirtyCanvas(true, true);
    }
  } catch (error) {
    alert(`폴더 목록을 불러오지 못했습니다: ${error.message}`);
  }
}

app.registerExtension({
  name: "KoreanOCR.EditableText",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name === "KoreanTextStyleSettings") {
      const originalCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        const result = originalCreated?.apply(this, arguments);
        const colors = [
          ["본문_색", "본문"],
          ["밑줄_색", "밑줄"],
          ["형광펜_색", "형광펜"],
          ["배경_색", "배경"],
        ];
        for (const [widgetName, label] of colors) {
          const button = this.addWidget("button", `${label} 색상표 열기`, null, () => {
            const widget = this.widgets?.find((w) => w.name === widgetName);
            if (!widget) return;
            const picker = document.createElement("input");
            picker.type = "color";
            picker.value = /^#[0-9a-f]{6}$/i.test(widget.value) ? widget.value : "#000000";
            picker.addEventListener("input", () => {
              widget.value = picker.value.toUpperCase();
              app.graph.setDirtyCanvas(true, true);
            });
            picker.click();
          });
          button.serialize = false;
        }
        return result;
      };
      return;
    }

    const batchFolderButtons = {
      KoreanBatchImagesToText: [
        ["사진_폴더", "input", "OCR할 사진 폴더 선택"],
        ["텍스트_저장_폴더", "output", "텍스트 저장 폴더 선택"],
      ],
      KoreanBatchTextToImages: [
        ["텍스트_폴더", "output", "수정한 텍스트 폴더 선택"],
        ["이미지_저장_폴더", "output", "이미지 저장 폴더 선택"],
      ],
    };
    if (batchFolderButtons[nodeData.name]) {
      const originalCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        const result = originalCreated?.apply(this, arguments);
        for (const [widgetName, kind, label] of batchFolderButtons[nodeData.name]) {
          const button = this.addWidget("button", `${label}…`, null, () => {
            pickComfyFolder(this, widgetName, kind, label);
          });
          button.serialize = false;
        }
        return result;
      };
      return;
    }

    if (nodeData.name !== "KoreanEditableText") return;

    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = originalCreated?.apply(this, arguments);
      const resetButton = this.addWidget("button", "AI 교정본으로 재설정", null, () => {
        const widget = this.widgets?.find((w) => w.name === "수정_텍스트");
        if (widget && typeof this._lastKoreanOCRText === "string") {
          widget.value = this._lastKoreanOCRText;
          app.graph.setDirtyCanvas(true, true);
        }
      });
      resetButton.serialize = false;
      return result;
    };

    const originalExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      originalExecuted?.apply(this, arguments);
      const source = message?.source_text?.[0];
      if (typeof source !== "string") return;
      const widget = this.widgets?.find((w) => w.name === "수정_텍스트");
      if (!widget) return;
      const previousSource = this._lastKoreanOCRText;
      this._lastKoreanOCRText = source;
      // Populate on first extraction, but never overwrite a user's correction.
      if (!widget.value || widget.value === previousSource) {
        widget.value = source;
        app.graph.setDirtyCanvas(true, true);
      }
    };
  },
});
