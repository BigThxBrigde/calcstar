"use strict";

/* CalcStar Toast 组件：成功 / 错误 / 信息 三种提示 */
window.CS = window.CS || {};

CS.toast = (function () {
  const DEFAULT_DURATION = 2600;

  const ICONS = {
    success: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>',
    error: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z"/></svg>',
    info: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>'
  };

  let container = null;

  function ensureContainer() {
    if (container && document.body.contains(container)) {
      return container;
    }
    container = document.createElement("div");
    container.className = "toast-container";
    container.setAttribute("aria-live", "polite");
    document.body.appendChild(container);
    return container;
  }

  function show(type, message, duration) {
    const host = ensureContainer();
    const item = document.createElement("div");
    item.className = "toast toast-" + type;
    item.innerHTML =
      '<span class="toast-icon">' + (ICONS[type] || ICONS.info) + "</span>" +
      '<span class="toast-text"></span>';
    item.querySelector(".toast-text").textContent = message;

    const ttl = typeof duration === "number" ? duration : DEFAULT_DURATION;
    let done = false;
    const timer = setTimeout(remove, ttl);

    function remove() {
      if (done) {
        return;
      }
      done = true;
      clearTimeout(timer);
      item.classList.add("toast-out");
      item.addEventListener("animationend", function () {
        item.remove();
      });
      // 动效被禁用（prefers-reduced-motion）时 animationend 不触发，兜底移除
      setTimeout(function () {
        item.remove();
      }, 400);
    }

    item.addEventListener("click", remove);
    host.appendChild(item);
    return item;
  }

  return {
    success: function (message, duration) {
      return show("success", message, duration);
    },
    error: function (message, duration) {
      return show("error", message, duration);
    },
    info: function (message, duration) {
      return show("info", message, duration);
    }
  };
})();
