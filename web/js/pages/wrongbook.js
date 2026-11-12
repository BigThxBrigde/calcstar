"use strict";

/* CalcStar 错题集页（Task 8.2/8.3）：错题列表、类别筛选、排序切换、
 * 从错题本一键"重新练习"。
 *
 * 依赖（script 加载顺序需在 api.js / router.js / toast.js / state.js 之后）：
 *   CS.api.callBridge(method, payload) -> Promise<data>
 *   CS.router.showPage(id)
 *   CS.toast.success / error / info
 *   CS.state
 *
 * 读写的 state 字段：
 *   读 CS.state.wrongBookCache      —— 本页列表缓存
 *       {category, orderBy, items}
 *   读 CS.state.wrongBookCacheDirty —— 缓存失效标记（约定名）：
 *       其他页面（如结果页订正全对后）置 true；本页显示时若为 true 则
 *       清空缓存并全量重拉，拉取成功后写回 wrongBookCache 并置回 false。
 *   写 CS.state.wrongBookCache      —— 每次拉取成功后更新
 *   写 CS.state.wrongBookCacheDirty —— 仅置回 false（失效处理）
 *
 * 「重新练习」成功后按 settings.js 的同结构写入做题页约定字段：
 *   CS.state.currentSession = create_practice_from_wrong_book 返回值
 *   CS.state.config = {category, range_n, count, duration_minutes,
 *                      allow_negative, include_parentheses, per_page}
 *   CS.state.answers = {}；CS.state.startedAt = Date.now()
 *   并 CS.router.showPage("page-practice")
 *
 * 后端接口（src/calcstar/bridge/api.py 与 practice_service.py）：
 *   list_wrong_book({category, order_by})
 *     category: 7 类之一或缺省（全部）；order_by: "wrong_count"(默认)
 *     或 "last_wrong_at"。返回条目含
 *     {id, expression, answer, category, range_n, wrong_count, last_wrong_at}
 *   create_practice_from_wrong_book({category?, count?, range_n?,
 *     duration_minutes?, allow_negative?, include_parentheses?, per_page?})
 *     count 缺省时取该筛选下全部错题（最多 MAX_COUNT=200 截断）。
 *     返回结构同 create_practice，另附 source:"wrong_book"。
 */

window.CS = window.CS || {};
CS.pages = CS.pages || {};

CS.pages.wrongbook = (function () {
  const MAX_COUNT = 200;      // 与后端 config.MAX_COUNT 一致
  const PER_PAGE = 10;        // 与后端 DEFAULT_PER_PAGE 一致

  const CATEGORY_LABELS = {
    add: "加法",
    sub: "减法",
    add_sub: "加减法",
    mul: "乘法",
    div: "除法",
    mul_div: "乘除法",
    mixed: "四则混合"
  };

  const els = {};
  let filterCategory = "";    // "" 表示全部
  let orderBy = "wrong_count";
  let items = [];             // 当前筛选下条目
  let loading = false;
  let retrying = false;
  let silentTimer = null;

  function $(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** "2026-11-12T10:30:00" -> "2026-11-12 10:30" */
  function formatDateTime(iso) {
    if (!iso || typeof iso !== "string") {
      return "—";
    }
    return iso.replace("T", " ").slice(0, 16);
  }

  /* ---------------- DOM 构建 ---------------- */

  function buildSkeleton() {
    const host = $("page-wrongbook");
    if (!host || host.dataset.built === "1") {
      return;
    }
    host.dataset.built = "1";

    const catOptions = ['<option value="">全部类别</option>'].concat(
      Object.keys(CATEGORY_LABELS).map(function (key) {
        return '<option value="' + key + '">' + CATEGORY_LABELS[key] + "</option>";
      })
    ).join("");

    host.innerHTML =
      '<div class="his-head">' +
      '  <button type="button" id="wrong-back-home" class="page-back-btn">🏠 返回首页</button>' +
      '  <div class="page-tabs" role="tablist" aria-label="记录页切换">' +
      '    <button type="button" class="page-tab" id="wrong-tab-history">历史成绩</button>' +
      '    <button type="button" class="page-tab is-active" id="wrong-tab-self" aria-current="page">错题本</button>' +
      "  </div>" +
      "</div>" +

      '<div class="card wrong-card">' +
      '  <h2 class="card-title">' +
      '    <svg class="ticon" viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>' +
      "    错题本" +
      "  </h2>" +
      '  <div class="wrong-toolbar">' +
      '    <label class="wrong-select-label" for="wrong-category">筛选类别</label>' +
      '    <select id="wrong-category" class="wrong-select">' + catOptions + "</select>" +
      '    <div class="wrong-sort" role="radiogroup" aria-label="排序方式">' +
      '      <button type="button" class="sort-btn is-active" data-order="wrong_count">按错误次数</button>' +
      '      <button type="button" class="sort-btn" data-order="last_wrong_at">按最近做错</button>' +
      "    </div>" +
      '    <button type="button" class="btn-wrong-retry" id="wrong-retry">' +
      "      🎯 重新练习" +
      "    </button>" +
      "  </div>" +
      '  <div class="wrong-columns" aria-hidden="true">' +
      "    <span>算式</span><span>正确答案</span><span>错误次数</span><span>最近做错</span>" +
      "  </div>" +
      '  <div id="wrong-list" role="list"></div>' +
      "</div>";

    $("wrong-back-home").addEventListener("click", function () {
      CS.router.showPage("page-settings");
    });
    $("wrong-tab-history").addEventListener("click", function () {
      CS.router.showPage("page-history");
    });
    $("wrong-category").addEventListener("change", function () {
      filterCategory = this.value;
      load();
    });
    els.sortBtns = host.querySelectorAll(".sort-btn");
    els.sortBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (btn.dataset.order === orderBy) {
          return;
        }
        orderBy = btn.dataset.order;
        els.sortBtns.forEach(function (b) {
          b.classList.toggle("is-active", b === btn);
        });
        load();
      });
    });
    $("wrong-retry").addEventListener("click", startRetryPractice);
  }

  /* ---------------- 列表 ---------------- */

  function renderList(list) {
    items = Array.isArray(list) ? list : [];

    if (items.length === 0) {
      els.list.innerHTML =
        '<div class="his-empty">' +
        '  <span class="his-empty-icon" aria-hidden="true">🎉</span>' +
        "  <p class=\"his-empty-title\">太棒啦，这里没有错题！</p>" +
        "  <p class=\"his-empty-tip\">继续保持，你是最棒的口算小达人～</p>" +
        "</div>";
      els.retry.disabled = true;
      return;
    }

    const rows = items.map(function (row) {
      return (
        '<div class="wrong-row" role="listitem">' +
        '  <span class="wrong-expr">' + esc(row.expression) + " ?</span>" +
        '  <span class="wrong-answer"><b>' + esc(row.answer) + "</b></span>" +
        '  <span class="wrong-count"><i class="wrong-count-num">' + esc(Number(row.wrong_count) || 0) + "</i> 次</span>" +
        '  <span class="wrong-time">' + esc(formatDateTime(row.last_wrong_at)) + "</span>" +
        "</div>"
      );
    });
    els.list.innerHTML = rows.join("");
    els.retry.disabled = false;
  }

  function renderLoading() {
    els.list.innerHTML =
      '<div class="his-loading"><span class="his-spinner" aria-hidden="true"></span>正在加载错题本…</div>';
    els.retry.disabled = true;
  }

  function renderError(message) {
    els.list.innerHTML =
      '<div class="his-empty"><p class="his-empty-title">加载失败啦～</p>' +
      "<p class=\"his-empty-tip\">" + esc(message) + "</p></div>";
    els.retry.disabled = true;
  }

  async function load(options) {
    const opts = options || {};
    if (loading) {
      return;
    }
    loading = true;
    if (!opts.silent) {
      renderLoading();
    }

    const payload = { order_by: orderBy };
    if (filterCategory) {
      payload.category = filterCategory;
    }

    try {
      const list = await CS.api.callBridge("list_wrong_book", payload);
      CS.state.wrongBookCache = {
        category: filterCategory,
        orderBy: orderBy,
        items: Array.isArray(list) ? list : []
      };
      CS.state.wrongBookCacheDirty = false;
      renderList(list);
    } catch (err) {
      if (!opts.silent) {
        renderError(err && err.message ? err.message : "请稍后重试");
        CS.toast.error(err && err.message ? err.message : "加载错题本失败");
      }
    } finally {
      loading = false;
    }
  }

  /* ---------------- 重新练习 ---------------- */

  async function startRetryPractice() {
    if (retrying || items.length === 0) {
      return;
    }
    retrying = true;
    const retryBtn = els.retry;
    retryBtn.disabled = true;
    const originalLabel = retryBtn.textContent;
    retryBtn.textContent = "正在生成…";

    const payload = { per_page: PER_PAGE };
    if (filterCategory) {
      payload.category = filterCategory;
    }
    payload.count = Math.min(items.length, MAX_COUNT);

    try {
      const data = await CS.api.callBridge(
        "create_practice_from_wrong_book", payload
      );
      // 与 settings.js 写入结构保持一致，供做题页/结果页使用
      CS.state.currentSession = data;
      CS.state.config = {
        category: data.category,
        range_n: data.range_n,
        count: data.total_count,
        duration_minutes: null,
        allow_negative: false,
        include_parentheses: false,
        per_page: data.per_page
      };
      CS.state.answers = {};
      CS.state.startedAt = Date.now();
      CS.router.showPage("page-practice");
      CS.toast.success("错题练习已生成，把它们全部打败吧！");
    } catch (err) {
      CS.toast.error(err && err.message ? err.message : "生成错题练习失败，请重试");
    } finally {
      retrying = false;
      retryBtn.disabled = false;
      retryBtn.textContent = originalLabel;
    }
  }

  /* ---------------- 显示/刷新策略 ---------------- */

  /** 页面显示时：缓存脏 → 全量重拉；否则先渲染缓存再后台静默刷新 */
  function onShown() {
    buildSkeleton();

    // 恢复上次筛选（缓存里记录了筛选条件）
    const cache = CS.state.wrongBookCache;
    if (cache) {
      if ((cache.category || "") !== filterCategory) {
        filterCategory = cache.category || "";
        els.category.value = filterCategory;
      }
      if (cache.orderBy && cache.orderBy !== orderBy) {
        orderBy = cache.orderBy;
        els.sortBtns.forEach(function (b) {
          b.classList.toggle("is-active", b.dataset.order === orderBy);
        });
      }
    }

    if (CS.state.wrongBookCacheDirty) {
      CS.state.wrongBookCache = null;
      CS.state.wrongBookCacheDirty = false;
      load();
      return;
    }

    if (cache && Array.isArray(cache.items) &&
        cache.category === filterCategory && cache.orderBy === orderBy) {
      renderList(cache.items);
    } else {
      load();
      return;
    }

    // 静默刷新：短暂延迟合并连续切页，避免竞态
    if (silentTimer) {
      clearTimeout(silentTimer);
    }
    silentTimer = setTimeout(function () {
      silentTimer = null;
      load({ silent: true });
    }, 200);
  }

  function init() {
    const host = $("page-wrongbook");
    if (!host || host.dataset.inited === "1") {
      return;
    }
    host.dataset.inited = "1";
    buildSkeleton();

    els.list = $("wrong-list");
    els.retry = $("wrong-retry");
    els.category = $("wrong-category");
    if (!els.sortBtns) {
      els.sortBtns = host.querySelectorAll(".sort-btn");
    }

    // 监听路由激活（router.js 不可修改，用 class 变化感知切页）
    const observer = new MutationObserver(function () {
      if (host.classList.contains("active")) {
        onShown();
      }
    });
    observer.observe(host, { attributes: true, attributeFilter: ["class"] });

    if (host.classList.contains("active")) {
      onShown();
    }
  }

  init();

  return {
    init: init,
    reload: load
  };
})();
