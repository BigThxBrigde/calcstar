"use strict";

/* CalcStar 错题集页：错题列表、类别筛选、排序切换、分页（每页条数取设置页
 * 保存的每页题数）、单条删除、清空与一键"重新练习"。
 *
 * 依赖（script 加载顺序需在 api.js / router.js / toast.js / state.js 之后）：
 *   CS.api.callBridge(method, payload) -> Promise<data>
 *   CS.router.showPage(id)
 *   CS.toast.success / error / info
 *   CS.state
 *
 * 读写的 state 字段：
 *   读 CS.state.wrongBookCache      —— 本页列表缓存
 *       {category, orderBy, page, pageSize, total, items}
 *   读 CS.state.wrongBookCacheDirty —— 缓存失效标记；为 true 时清空缓存并
 *       重新拉取，拉取成功后写回缓存并置回 false。
 *   写 CS.state.currentSession / config / answers / startedAt —— 重新练习。
 *
 * 后端接口（src/calcstar/bridge/api.py）：
 *   get_settings({}) -> 设置字典，其中 per_page 用于分页大小
 *   list_wrong_book_page({category, order_by, page, page_size})
 *     -> {items, total, page, page_size}
 *   delete_wrong_book_entry({id}) -> {deleted: true}
 *   clear_wrong_book({}) -> {deleted: 条数}
 *   create_practice_from_wrong_book({category?, count?, per_page?})
 *     -> 结构同 create_practice，另附 source:"wrong_book"
 */

window.CS = window.CS || {};
CS.pages = CS.pages || {};

CS.pages.wrongbook = (function () {
  const MAX_COUNT = 200;        // 与后端 config.MAX_COUNT 一致
  const DEFAULT_PER_PAGE = 10;  // get_settings 无 per_page 时的兜底
  const CONFIRM_MS = 4000;      // 二次确认按钮自动复位时长

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
  let filterCategory = "";      // "" 表示全部
  let orderBy = "wrong_count";
  let page = 1;
  let pageSize = DEFAULT_PER_PAGE;
  let total = 0;
  let items = [];               // 当前页条目
  let loading = false;
  let retrying = false;
  let silentTimer = null;
  let rowDeleting = false;
  let deleteArmedSpan = null;
  let deleteTimer = null;
  let clearArmed = false;
  let clearing = false;
  let clearTimer = null;

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

      '<div class="card wb-card">' +
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
      '  <div class="wb-columns" aria-hidden="true">' +
      "    <span>算式</span><span>正确答案</span><span>错误次数</span><span>最近做错</span><span>操作</span>" +
      "  </div>" +
      '  <div id="wrong-list" role="list"></div>' +
      '  <div class="his-pager hidden" id="wrong-pager">' +
      '    <button type="button" class="pager-btn" id="wrong-prev">上一页</button>' +
      '    <span class="pager-info" id="wrong-pageinfo"></span>' +
      '    <button type="button" class="pager-btn" id="wrong-next">下一页</button>' +
      "  </div>" +
      '  <div class="his-clear-row hidden" id="wrong-clear-row">' +
      '    <button type="button" class="his-clear-btn" id="wrong-clear">清空错题本</button>' +
      "  </div>" +
      "</div>";

    $("wrong-back-home").addEventListener("click", function () {
      CS.router.showPage("page-settings");
    });
    $("wrong-tab-history").addEventListener("click", function () {
      CS.router.showPage("page-history");
    });
    $("wrong-category").addEventListener("change", function () {
      filterCategory = this.value;
      page = 1;
      loadPage(1);
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
        page = 1;
        loadPage(1);
      });
    });
    $("wrong-retry").addEventListener("click", startRetryPractice);
    $("wrong-prev").addEventListener("click", function () {
      gotoPage(page - 1);
    });
    $("wrong-next").addEventListener("click", function () {
      gotoPage(page + 1);
    });
    $("wrong-clear").addEventListener("click", clearWrongBook);
  }

  /* ---------------- 列表 ---------------- */

  function totalPagesOf() {
    return Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
  }

  function hidePagerAndClear() {
    els.pager.classList.add("hidden");
    els.clearRow.classList.add("hidden");
  }

  function renderList(data) {
    items = Array.isArray(data.items) ? data.items : [];
    total = Number(data.total) || 0;
    page = Number(data.page) || 1;

    if (total === 0 || items.length === 0) {
      els.list.innerHTML =
        '<div class="his-empty">' +
        '  <span class="his-empty-icon" aria-hidden="true">🎉</span>' +
        "  <p class=\"his-empty-title\">太棒啦，这里没有错题！</p>" +
        "  <p class=\"his-empty-tip\">继续保持，你是最棒的口算小达人～</p>" +
        "</div>";
      hidePagerAndClear();
      els.retry.disabled = true;
      return;
    }

    els.pager.classList.remove("hidden");
    els.clearRow.classList.remove("hidden");

    const rows = items.map(function (row) {
      return (
        '<div class="wb-row" role="listitem">' +
        '  <span class="wrong-expr">' + esc(row.expression) + "</span>" +
        '  <span class="wrong-answer"><b>' + esc(row.answer) + "</b></span>" +
        '  <span class="wrong-count"><i class="wrong-count-num">' + esc(Number(row.wrong_count) || 0) + "</i> 次</span>" +
        '  <span class="wrong-time">' + esc(formatDateTime(row.last_wrong_at)) + "</span>" +
        '  <span class="wrong-actions">' +
        '    <span class="his-act his-act-del" role="button" data-act="del" data-id="' + Number(row.id) + '" title="删除这条错题">删除</span>' +
        "  </span>" +
        "</div>"
      );
    });
    els.list.innerHTML = rows.join("");
    els.pageinfo.textContent = "第 " + page + " / " + totalPagesOf() + " 页 · 共 " + total + " 条";
    els.prev.disabled = page <= 1;
    els.next.disabled = page >= totalPagesOf();
    els.retry.disabled = false;

    els.list.querySelectorAll(".his-act-del").forEach(function (span) {
      span.addEventListener("click", function (ev) {
        ev.stopPropagation();
        deleteEntry(Number(span.dataset.id), span);
      });
    });
  }

  function renderLoading() {
    els.list.innerHTML =
      '<div class="his-loading"><span class="his-spinner" aria-hidden="true"></span>正在加载错题本…</div>';
    hidePagerAndClear();
    els.retry.disabled = true;
  }

  function renderError(message) {
    els.list.innerHTML =
      '<div class="his-empty"><p class="his-empty-title">加载失败啦～</p>' +
      "<p class=\"his-empty-tip\">" + esc(message) + "</p></div>";
    hidePagerAndClear();
    els.retry.disabled = true;
  }

  /** 每页条数取设置页保存的 per_page；读取失败回退到当前会话或默认值 */
  async function ensurePageSize() {
    try {
      const settings = await CS.api.callBridge("get_settings", {});
      const saved = Number(settings && settings.per_page);
      if (Number.isFinite(saved) && saved >= 1) {
        pageSize = Math.floor(saved);
        return;
      }
    } catch (err) {
      // 读取设置失败时走下方兜底
    }
    const configured = CS.state.config && Number(CS.state.config.per_page);
    pageSize = Number.isFinite(configured) && configured >= 1
      ? Math.floor(configured)
      : DEFAULT_PER_PAGE;
  }

  async function loadPage(targetPage, options) {
    const opts = options || {};
    if (loading) {
      return;
    }
    const want = Math.max(1, Math.floor(targetPage) || 1);
    loading = true;
    if (!opts.silent) {
      renderLoading();
    }

    const payload = { order_by: orderBy, page: want, page_size: pageSize };
    if (filterCategory) {
      payload.category = filterCategory;
    }

    try {
      const data = await CS.api.callBridge("list_wrong_book_page", payload);
      page = Number(data.page) || want;
      total = Number(data.total) || 0;
      const size = Number(data.page_size) || pageSize;
      CS.state.wrongBookCache = {
        category: filterCategory,
        orderBy: orderBy,
        page: page,
        pageSize: size,
        total: total,
        items: Array.isArray(data.items) ? data.items : []
      };
      CS.state.wrongBookCacheDirty = false;
      renderList(data);
    } catch (err) {
      if (!opts.silent) {
        renderError(err && err.message ? err.message : "请稍后重试");
        CS.toast.error(err && err.message ? err.message : "加载错题本失败");
      }
    } finally {
      loading = false;
    }
  }

  function gotoPage(target) {
    if (target < 1 || target > totalPagesOf()) {
      return;
    }
    loadPage(target);
  }

  /* ---------------- 单条删除 / 清空 ---------------- */

  function disarmRowDelete(span) {
    if (deleteArmedSpan === span) {
      deleteArmedSpan = null;
    }
    if (deleteTimer) {
      clearTimeout(deleteTimer);
      deleteTimer = null;
    }
    if (span) {
      span.textContent = "删除";
      span.classList.remove("is-armed");
    }
  }

  /** 两步确认后删除单条错题；4 秒未确认自动复位 */
  async function deleteEntry(id, span) {
    if (rowDeleting || clearing) {
      return;
    }
    if (deleteArmedSpan && deleteArmedSpan !== span) {
      disarmRowDelete(deleteArmedSpan);
    }
    if (deleteArmedSpan !== span) {
      deleteArmedSpan = span;
      span.textContent = "确认删除";
      span.classList.add("is-armed");
      if (deleteTimer) {
        clearTimeout(deleteTimer);
      }
      deleteTimer = setTimeout(function () {
        disarmRowDelete(span);
      }, CONFIRM_MS);
      return;
    }

    rowDeleting = true;
    disarmRowDelete(span);
    try {
      await CS.api.callBridge("delete_wrong_book_entry", { id: id });
      CS.toast.success("已删除该条错题");
      CS.state.wrongBookCache = null;
      CS.state.wrongBookCacheDirty = true;
      // 当前页删空且不是第一页时回退一页，避免停在没有内容的页上
      const target = items.length === 1 && page > 1 ? page - 1 : page;
      await loadPage(target);
    } catch (err) {
      CS.toast.error(err && err.message ? err.message : "删除失败，请重试");
    } finally {
      rowDeleting = false;
    }
  }

  function disarmClear() {
    clearArmed = false;
    if (clearTimer) {
      clearTimeout(clearTimer);
      clearTimer = null;
    }
    if (els.clearBtn) {
      els.clearBtn.textContent = "清空错题本";
      els.clearBtn.classList.remove("is-armed");
    }
  }

  /** 两步确认后清空全部错题（练习历史保留） */
  async function clearWrongBook() {
    if (clearing || rowDeleting) {
      return;
    }
    if (!clearArmed) {
      clearArmed = true;
      els.clearBtn.textContent = "再点一次确认清空";
      els.clearBtn.classList.add("is-armed");
      if (clearTimer) {
        clearTimeout(clearTimer);
      }
      clearTimer = setTimeout(disarmClear, CONFIRM_MS);
      return;
    }
    disarmClear();
    if (deleteArmedSpan) {
      disarmRowDelete(deleteArmedSpan);
    }

    clearing = true;
    els.clearBtn.disabled = true;
    try {
      const res = await CS.api.callBridge("clear_wrong_book", {});
      CS.toast.success("已清空 " + (Number(res.deleted) || 0) + " 条错题");
      CS.state.wrongBookCache = null;
      CS.state.wrongBookCacheDirty = true;
      page = 1;
      await loadPage(1);
    } catch (err) {
      CS.toast.error(err && err.message ? err.message : "清空错题本失败，请重试");
    } finally {
      clearing = false;
      els.clearBtn.disabled = false;
    }
  }

  /* ---------------- 重新练习 ---------------- */

  async function startRetryPractice() {
    if (retrying || total === 0) {
      return;
    }
    retrying = true;
    const retryBtn = els.retry;
    retryBtn.disabled = true;
    const originalLabel = retryBtn.textContent;
    retryBtn.textContent = "正在生成…";

    const payload = { per_page: pageSize };
    if (filterCategory) {
      payload.category = filterCategory;
    }
    payload.count = Math.min(total, MAX_COUNT);

    try {
      const data = await CS.api.callBridge(
        "create_practice_from_wrong_book", payload
      );
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

  /** 页面显示时：恢复筛选与分页大小，缓存脏则重拉，否则渲染缓存并静默刷新 */
  async function onShown() {
    buildSkeleton();

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

    await ensurePageSize();

    if (CS.state.wrongBookCacheDirty) {
      CS.state.wrongBookCache = null;
      CS.state.wrongBookCacheDirty = false;
      page = 1;
      loadPage(1);
      return;
    }

    if (cache && Array.isArray(cache.items) &&
        cache.category === filterCategory && cache.orderBy === orderBy &&
        Number(cache.pageSize) === pageSize) {
      page = Number(cache.page) || 1;
      total = Number(cache.total) || 0;
      renderList({
        items: cache.items, total: total, page: page, page_size: pageSize
      });
    } else {
      loadPage(page);
      return;
    }

    // 静默刷新：短暂延迟合并连续切页，避免竞态
    if (silentTimer) {
      clearTimeout(silentTimer);
    }
    silentTimer = setTimeout(function () {
      silentTimer = null;
      loadPage(page, { silent: true });
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
    els.pager = $("wrong-pager");
    els.prev = $("wrong-prev");
    els.next = $("wrong-next");
    els.pageinfo = $("wrong-pageinfo");
    els.clearRow = $("wrong-clear-row");
    els.clearBtn = $("wrong-clear");
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
    reload: loadPage
  };
})();
