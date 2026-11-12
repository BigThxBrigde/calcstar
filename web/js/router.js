"use strict";

/* CalcStar 页面路由：showPage(id) 切换 .page.active，带切换动画 */
window.CS = window.CS || {};

CS.router = (function () {
  const PAGE_IDS = [
    "page-settings",
    "page-practice",
    "page-result",
    "page-history",
    "page-wrongbook"
  ];

  let currentPage = null;

  /**
   * 切换到指定页面。
   * @param {string} id 页面容器元素 id，如 "page-practice"
   * @returns {boolean} 是否切换成功
   */
  function showPage(id) {
    const target = document.getElementById(id);
    if (!target || PAGE_IDS.indexOf(id) === -1) {
      console.error("页面不存在：" + id);
      return false;
    }

    PAGE_IDS.forEach(function (pid) {
      const el = document.getElementById(pid);
      if (!el) {
        return;
      }
      el.classList.remove("active");
      if (pid === id) {
        // 移除后强制重排，再重新添加以重启动入场动画
        void el.offsetWidth;
        el.classList.add("active");
      }
    });

    currentPage = id;
    return true;
  }

  function currentPageId() {
    return currentPage;
  }

  return {
    PAGE_IDS: PAGE_IDS,
    showPage: showPage,
    currentPageId: currentPageId
  };
})();
