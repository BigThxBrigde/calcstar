"use strict";

/* CalcStar 全屏遮罩组件：阻塞操作期间展示 spinner + 文案 */
window.CS = window.CS || {};

CS.mask = (function () {
  let el = null;
  let textEl = null;

  function ensure() {
    if (el && document.body.contains(el)) {
      return;
    }
    el = document.createElement("div");
    el.className = "cs-mask";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    el.innerHTML =
      '<div class="cs-mask-box">' +
      '  <span class="cs-mask-spinner" aria-hidden="true"></span>' +
      '  <span class="cs-mask-text"></span>' +
      "</div>";
    textEl = el.querySelector(".cs-mask-text");
    document.body.appendChild(el);
  }

  return {
    /** 显示遮罩（可重复调用更新文案） */
    show(text) {
      ensure();
      textEl.textContent = text || "处理中…";
      el.classList.add("is-visible");
    },

    /** 隐藏遮罩（未显示时静默） */
    hide() {
      if (el) {
        el.classList.remove("is-visible");
      }
    },
  };
})();
