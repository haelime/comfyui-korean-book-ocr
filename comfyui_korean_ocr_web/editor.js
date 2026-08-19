import { app } from "/scripts/app.js";

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

    if (nodeData.name !== "KoreanEditableText") return;

    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = originalCreated?.apply(this, arguments);
      const resetButton = this.addWidget("button", "AI 선택본으로 재설정", null, () => {
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
