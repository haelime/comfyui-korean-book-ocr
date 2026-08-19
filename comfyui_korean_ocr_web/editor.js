import { app } from "/scripts/app.js";

app.registerExtension({
  name: "KoreanOCR.EditableText",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "KoreanEditableText") return;

    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = originalCreated?.apply(this, arguments);
      this.addWidget("button", "OCR 원문으로 재설정", null, () => {
        const widget = this.widgets?.find((w) => w.name === "edited_text");
        if (widget && typeof this._lastKoreanOCRText === "string") {
          widget.value = this._lastKoreanOCRText;
          app.graph.setDirtyCanvas(true, true);
        }
      });
      return result;
    };

    const originalExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      originalExecuted?.apply(this, arguments);
      const source = message?.ocr_text?.[0];
      if (typeof source !== "string") return;
      const widget = this.widgets?.find((w) => w.name === "edited_text");
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
