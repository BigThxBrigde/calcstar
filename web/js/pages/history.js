"use strict";

/* CalcStar 历史成绩页（Task 8.1）：分页列表、单次练习明细、空状态。
 *
 * 依赖（script 加载顺序需在 api.js / router.js / toast.js / state.js 之后）：
 *   CS.api.callBridge(method, payload) -> Promise<data>
 *   CS.router.showPage(id) / CS.router.currentPageId()
 *   CS.toast.success / error / info
 *   CS.state
 *
 * 读写的 state 字段：
 *   读 CS.state.historyCache        —— 本页列表缓存
 *       {page, pageSize, total, items}
 *   读 CS.state.historyCacheDirty   —— 缓存失效标记（约定名）：
 *       其他页面（如结果页订正全对后）置 true；本页显示时若为 true 则
 *       清空缓存并全量重拉，拉取成功后写回 historyCache 并置回 false。
 *   写 CS.state.historyCache        —— 每次拉取成功后更新
 *   写 CS.state.historyCacheDirty   —— 仅置回 false（失效处理）
 *
 * 本页每次显示都会后台静默刷新一次列表，保证数据最新；
 * 缓存仅用于"先渲染旧数据避免闪烁 + 失效时全屏加载态"。
 *
 * 后端接口（src/calcstar/bridge/api.py）：
 *   list_history({page, page_size}) -> {items,total,page,page_size}
 *     items 为 sessions 表整行（id/category/range_n/count/started_at/
 *     finished_at/duration_seconds/correct_count/total_count/score/
 *     status/passed 等）
 *   get_session_detail({session_id}) -> 会话行 + questions:
 *     [{seq, expression, answer, user_answer, is_correct, ...}]
 *   export_report({session_id, format}) -> {path} / {cancelled: true}
 *     format 为 pdf 或 png，默认 pdf。
 */

window.CS = window.CS || {};
CS.pages = CS.pages || {};

CS.pages.history = (function () {
  const PAGE_SIZE = 10;
  const MAX_PAGES = 9999;
  const CONFIRM_MS = 4000;  // 二次确认按钮自动复位时长

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
  let page = 1;          // 当前页码（列表）
  let listLoading = false;
  let detailLoading = false;
  let silentTimer = null;
  let clearArmed = false; // 清空按钮二次确认状态
  let rowRedoing = false;   // 行级重做进行中（防并发）
  let rowDeleting = false;  // 行级删除进行中（防并发）
  let deleteArmedSpan = null; // 删除二次确认中的按钮
  let deleteTimer = null;     // 删除确认自动复位延时器
  let clearTimer = null;
  let clearing = false;     // 清空历史进行中（防并发）
  let rowExporting = false; // 行级成绩单导出进行中（防并发）

  function $(id) {
    return document.getElementById(id);
  }

  /** HTML 转义，防注入 */
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

  /** 秒数 -> "1分23秒" / "45秒" */
  function formatDuration(seconds) {
    const n = Number(seconds);
    if (!Number.isFinite(n) || n < 0) {
      return "—";
    }
    const total = Math.round(n);
    const m = Math.floor(total / 60);
    const s = total % 60;
    if (m <= 0) {
      return s + "秒";
    }
    return m + "分" + (s > 0 ? String(s) + "秒" : "");
  }

  /** 数值范围 -> "20以内" */
  function formatRange(rangeN) {
    const n = Number(rangeN);
    return Number.isFinite(n) ? n + "以内" : "—";
  }

  /** 正确率文本（未提交返回 "—"） */
  function formatAccuracy(correct, total) {
    const c = Number(correct);
    const t = Number(total);
    if (!Number.isFinite(c) || !Number.isFinite(t) || t <= 0) {
      return "—";
    }
    return Math.round((c / t) * 100) + "%";
  }

  /** 会话状态徽章 HTML */
  function badgeHtml(row) {
    const status = row.status;
    if (status !== "submitted" && status !== "passed") {
      return '<span class="his-badge his-badge-doing">进行中</span>';
    }
    if (Number(row.passed) === 1) {
      return '<span class="his-badge his-badge-pass">★ 已通过</span>';
    }
    return '<span class="his-badge his-badge-miss">继续加油</span>';
  }

  /** 类别胶囊 */
  function categoryChip(category) {
    const label = CATEGORY_LABELS[category] || category || "未知";
    return '<span class="his-cat his-cat-' + esc(category) + '">' + esc(label) + "</span>";
  }

  /* ---------------- DOM 构建 ---------------- */

  function buildSkeleton() {
    const host = $("page-history");
    if (!host || host.dataset.built === "1") {
      return;
    }
    host.dataset.built = "1";
    host.innerHTML =
      '<div class="his-head">' +
      '  <button type="button" id="history-back-home" class="page-back-btn">🏠 返回首页</button>' +
      '  <div class="page-tabs" role="tablist" aria-label="记录页切换">' +
      '    <button type="button" class="page-tab is-active" id="history-tab-self" aria-current="page">历史成绩</button>' +
      '    <button type="button" class="page-tab" id="history-tab-wrong">错题本</button>' +
      "  </div>" +
      "</div>" +

      // 列表视图
      '<div class="card his-card" id="history-list-view">' +
      '  <h2 class="card-title">' +
      '    <svg class="ticon" viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z"/></svg>' +
      "    历史成绩" +
      "  </h2>" +
      '  <div class="his-columns" aria-hidden="true">' +
      '    <span>日期时间</span><span>类别</span><span>范围</span><span>题量</span>' +
      "    <span>得分</span><span>正确率</span><span>用时</span><span>状态</span><span>操作</span>" +
      "  </div>" +
      '  <div id="history-list" role="list"></div>' +
      '  <div class="his-pager" id="history-pager">' +
      '    <button type="button" class="pager-btn" id="history-prev">← 上一页</button>' +
      '    <span class="pager-info" id="history-pageinfo"></span>' +
      '    <button type="button" class="pager-btn" id="history-next">下一页 →</button>' +
      "  </div>" +
      '  <div class="his-clear-row" id="history-clear-row">' +
      '    <button type="button" class="his-clear-btn" id="history-clear">清空历史</button>' +
      "  </div>" +
      "</div>" +

      // 明细视图（默认隐藏）
      '<div class="card his-card hidden" id="history-detail-view">' +
      '  <div class="his-detail-head">' +
      '    <button type="button" class="pager-btn" id="history-detail-back">← 返回列表</button>' +
      '    <div class="his-detail-summary" id="history-detail-summary"></div>' +
      "  </div>" +
      '  <div id="history-detail-questions" class="his-detail-list"></div>' +
      "</div>";

    $("history-back-home").addEventListener("click", function () {
      CS.router.showPage("page-settings");
    });
    $("history-tab-wrong").addEventListener("click", function () {
      CS.router.showPage("page-wrongbook");
    });
    $("history-prev").addEventListener("click", function () {
      gotoPage(page - 1);
    });
    $("history-next").addEventListener("click", function () {
      gotoPage(page + 1);
    });
    $("history-detail-back").addEventListener("click", function () {
      showListView();
    });
    $("history-clear").addEventListener("click", function () {
      clearHistory();
    });
  }

  /* ---------------- 列表 ---------------- */

  function showListView() {
    els.detailView.classList.add("hidden");
    els.listView.classList.remove("hidden");
  }

  function showDetailView() {
    els.listView.classList.add("hidden");
    els.detailView.classList.remove("hidden");
  }

  function renderList(data) {
    const items = Array.isArray(data.items) ? data.items : [];
    const total = Number(data.total) || 0;
    const pageSize = Number(data.page_size) || PAGE_SIZE;
    const totalPages = Math.max(1, Math.min(MAX_PAGES, Math.ceil(total / pageSize)));

    if (total === 0 || items.length === 0) {
      els.list.innerHTML =
        '<div class="his-empty">' +
        '  <span class="his-empty-icon" aria-hidden="true">📭</span>' +
        "  <p class=\"his-empty-title\">这里空空如也～</p>" +
        "  <p class=\"his-empty-tip\">快去首页开始第一次口算练习吧！</p>" +
        "</div>";
      els.pager.classList.add("hidden");
      els.clearRow.classList.add("hidden");
      return;
    }

    els.pager.classList.remove("hidden");
    els.clearRow.classList.remove("hidden");
    const rows = items.map(function (row) {
      const submitted = row.status === "submitted" || row.status === "passed";
      const score = submitted && row.score != null ? row.score + "分" : "—";
      const cls = (Number(row.passed) === 1) ? " is-pass" : "";
      return (
        '<button type="button" class="his-row' + cls + '" role="listitem" data-session-id="' + Number(row.id) + '"' +
        ' aria-label="查看 ' + esc(formatDateTime(row.started_at)) + " " + esc(CATEGORY_LABELS[row.category] || "") + ' 的练习明细">' +
        '  <span class="his-cell his-time">' + esc(formatDateTime(row.started_at)) + "</span>" +
        "  <span class=\"his-cell\">" + categoryChip(row.category) + "</span>" +
        '  <span class="his-cell">' + esc(formatRange(row.range_n)) + "</span>" +
        '  <span class="his-cell">' + esc(Number(row.count) || 0) + "题</span>" +
        '  <span class="his-cell his-strong">' + esc(score) + "</span>" +
        '  <span class="his-cell">' + esc(formatAccuracy(row.correct_count, row.total_count)) + "</span>" +
        '  <span class="his-cell">' + esc(formatDuration(row.duration_seconds)) + "</span>" +
        '  <span class="his-cell">' + badgeHtml(row) + "</span>" +
        '  <span class="his-cell"><span class="his-actions">' +
        '<span class="his-act his-act-export" role="button" data-act="export" data-session-id="' + Number(row.id) + '" title="导出本次成绩单 PDF">PDF</span>' +
        '<span class="his-act his-act-export" role="button" data-act="export-png" data-session-id="' + Number(row.id) + '" title="导出本次成绩单 PNG 图片">图片</span>' +
        '<span class="his-act his-act-redo" role="button" data-act="redo" data-session-id="' + Number(row.id) + '" title="按本次的设置重新生成一局练习">重做</span>' +
        '<span class="his-act his-act-del" role="button" data-act="del" data-session-id="' + Number(row.id) + '" title="删除这条练习记录（错题本保留）">删除</span>' +
        "</span></span>" +
        "</button>"
      );
    });
    els.list.innerHTML = rows.join("");

    els.pageinfo.textContent = "第 " + data.page + " / " + totalPages + " 页 · 共 " + total + " 条";
    els.prev.disabled = data.page <= 1;
    els.next.disabled = data.page >= totalPages;

    els.list.querySelectorAll(".his-row").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openDetail(Number(btn.dataset.sessionId));
      });
    });

    els.list.querySelectorAll(".his-act").forEach(function (span) {
      span.addEventListener("click", function (ev) {
        ev.stopPropagation();
        const act = span.dataset.act;
        const sessionId = Number(span.dataset.sessionId);
        if (act === "export" || act === "export-png") {
          exportRow(sessionId, span, act === "export-png" ? "png" : "pdf");
        } else if (act === "redo") {
          redoRow(sessionId, span);
        } else if (act === "del") {
          deleteRow(sessionId, span);
        }
      });
    });
  }

  function renderListLoading() {
    els.list.innerHTML =
      '<div class="his-loading"><span class="his-spinner" aria-hidden="true"></span>正在加载历史记录…</div>';
    els.pager.classList.add("hidden");
  }

  async function fetchPage(targetPage) {
    const data = await CS.api.callBridge("list_history", {
      page: targetPage,
      page_size: PAGE_SIZE
    });
    // 后端对越界页码不报错但可能返回空页，回退到有数据页
    if ((!Array.isArray(data.items) || data.items.length === 0) && data.total > 0 && targetPage > 1) {
      const totalPages = Math.max(1, Math.ceil(Number(data.total) / (Number(data.page_size) || PAGE_SIZE)));
      const safe = Math.min(targetPage, totalPages);
      if (safe !== targetPage) {
        return fetchPage(safe);
      }
    }
    return data;
  }

  async function loadPage(targetPage, options) {
    const opts = options || {};
    if (listLoading) {
      return;
    }
    const want = Math.max(1, Math.floor(targetPage) || 1);
    listLoading = true;
    if (!opts.silent) {
      renderListLoading();
    }
    try {
      const data = await fetchPage(want);
      page = Number(data.page) || want;
      CS.state.historyCache = {
        page: page,
        pageSize: Number(data.page_size) || PAGE_SIZE,
        total: Number(data.total) || 0,
        items: data.items
      };
      CS.state.historyCacheDirty = false;
      renderList(data);
    } catch (err) {
      if (!opts.silent) {
        els.list.innerHTML =
          '<div class="his-empty"><p class="his-empty-title">加载失败啦～</p>' +
          "<p class=\"his-empty-tip\">" + esc(err && err.message ? err.message : "请稍后重试") + "</p></div>";
        els.pager.classList.add("hidden");
        CS.toast.error(err && err.message ? err.message : "加载历史记录失败");
      }
    } finally {
      listLoading = false;
    }
  }

  function gotoPage(targetPage) {
    if (targetPage < 1) {
      return;
    }
    loadPage(targetPage);
  }

  /* ---------------- 行级成绩单导出 ---------------- */

  /** 按指定格式导出某一行的成绩单（弹出另存为对话框；防并发） */
  async function exportRow(sessionId, span, format) {
    if (rowExporting) {
      return;
    }
    rowExporting = true;
    const original = span.textContent;
    span.textContent = "导出中…";
    span.classList.add("is-busy");
    CS.mask.show("正在生成成绩单…");
    try {
      const res = await CS.api.callBridge("export_report", {
        session_id: sessionId,
        format: format,
      });
      if (res && res.cancelled) {
        CS.toast.info("已取消导出");
      } else if (res && res.path) {
        CS.toast.success("成绩单已保存：" + res.path);
      } else {
        CS.toast.error("导出失败，请重试");
      }
    } catch (err) {
      CS.toast.error(
        err && err.message ? err.message : "导出成绩单失败，请重试"
      );
    } finally {
      span.textContent = original;
      span.classList.remove("is-busy");
      rowExporting = false;
      CS.mask.hide();
    }
  }

  /* ---------------- 行级重做 ---------------- */

  /** 重做某次练习：重置原会话为未作答状态（题目保持原卷），不新建记录 */
  async function redoRow(sessionId, span) {
    if (rowRedoing) {
      return;
    }
    rowRedoing = true;
    const original = span.textContent;
    span.textContent = "生成中…";
    span.classList.add("is-busy");
    try {
      // 重置原会话（同一条记录原地复用，提交后更新该条历史）
      const data = await CS.api.callBridge("reset_practice", {
        session_id: sessionId,
      });
      if (CS.pages.practice && CS.pages.practice.resetSession) {
        CS.pages.practice.resetSession();
      }
      CS.state.currentSession = data;
      CS.state.config = null;
      CS.state.answers = {};
      CS.state.startedAt = Date.now();
      CS.router.showPage("page-practice");
      CS.toast.success("已重置本次练习，加油哦！");
    } catch (err) {
      CS.toast.error(
        err && err.message ? err.message : "重做失败，请重试"
      );
    } finally {
      span.textContent = original;
      span.classList.remove("is-busy");
      rowRedoing = false;
    }
  }

  /* ---------------- 行级删除 ---------------- */

  /** 退出某行的删除二次确认状态 */
  function disarmRowDelete(span) {
    if (deleteArmedSpan === span) {
      deleteArmedSpan = null;
    }
    if (deleteTimer) {
      clearTimeout(deleteTimer);
      deleteTimer = null;
    }
    span.textContent = "删除";
    span.classList.remove("is-armed");
  }

  /** 两步确认后删除单条练习记录（错题本保留）；4 秒未确认自动复位 */
  async function deleteRow(sessionId, span) {
    if (rowDeleting) {
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
      await CS.api.callBridge("delete_session", { session_id: sessionId });
      CS.toast.success("已删除该次练习记录，错题本保留");
      if (CS.state.historyCache) {
        CS.state.historyCacheDirty = true;
      }
      await loadPage(page, { silent: false });
    } catch (err) {
      CS.toast.error(err && err.message ? err.message : "删除失败，请重试");
    } finally {
      rowDeleting = false;
    }
  }

  /* ---------------- 清空历史 ---------------- */  /** 退出二次确认状态 */
  function disarmClear() {
    clearArmed = false;
    if (clearTimer) {
      clearTimeout(clearTimer);
      clearTimer = null;
    }
    els.clearBtn.textContent = "清空历史";
    els.clearBtn.classList.remove("is-armed");
  }

  /** 两步确认后清空全部练习历史（错题本保留） */
  async function clearHistory() {
    if (clearing || detailLoading || listLoading) {
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

    clearing = true;
    els.clearBtn.disabled = true;
    try {
      const res = await CS.api.callBridge("clear_history", {});
      CS.state.historyCache = null;
      CS.state.historyCacheDirty = true;
      CS.toast.success(
        "已清空 " + (Number(res.deleted) || 0) + " 次练习记录，错题本保留"
      );
      page = 1;
      await loadPage(1);
    } catch (err) {
      CS.toast.error(err && err.message ? err.message : "清空历史失败，请重试");
    } finally {
      clearing = false;
      els.clearBtn.disabled = false;
    }
  }

  /* ---------------- 明细 ---------------- */

  function renderDetailSummary(detail) {
    const submitted = detail.status === "submitted" || detail.status === "passed";
    const score = submitted && detail.score != null ? detail.score + " 分" : "—";
    els.detailSummary.innerHTML =
      "<span>" + categoryChip(detail.category) + "</span>" +
      "<span>范围 " + esc(formatRange(detail.range_n)) + "</span>" +
      "<span>共 " + esc(Number(detail.count) || 0) + " 题</span>" +
      "<span>得分 <b>" + esc(score) + "</b></span>" +
      "<span>正确率 <b>" + esc(formatAccuracy(detail.correct_count, detail.total_count)) + "</b></span>" +
      "<span>用时 <b>" + esc(formatDuration(detail.duration_seconds)) + "</b></span>" +
      badgeHtml(detail);
  }

  function questionRowHtml(q, index) {
    const answered = q.user_answer !== null && q.user_answer !== undefined;
    const correct = Number(q.is_correct) === 1;
    const graded = q.is_correct !== null && q.is_correct !== undefined;
    const stateClass = !graded ? " is-unknown" : correct ? " is-right" : " is-wrong";
    const mark = !graded ? "—" : correct ? "✓" : "✗";
    const userText = answered
      ? String(q.user_answer)
      : (graded ? "未作答" : "还没作答哦");

    return (
      '<div class="his-q' + stateClass + '">' +
      '  <span class="his-q-seq" aria-hidden="true">' + (index + 1) + "</span>" +
      '  <span class="his-q-expr">' + esc(q.expression) + "</span>" +
      '  <span class="his-q-user">你的答案：<b>' + esc(userText) + "</b></span>" +
      '  <span class="his-q-right">正确答案：<b>' + esc(q.answer) + "</b></span>" +
      '  <span class="his-q-mark" aria-hidden="true">' + mark + "</span>" +
      "</div>"
    );
  }

  async function openDetail(sessionId) {
    if (detailLoading) {
      return;
    }
    detailLoading = true;
    els.detailQuestions.innerHTML =
      '<div class="his-loading"><span class="his-spinner" aria-hidden="true"></span>正在加载练习明细…</div>';
    els.detailSummary.innerHTML = "";
    showDetailView();

    try {
      const detail = await CS.api.callBridge("get_session_detail", {
        session_id: sessionId
      });
      renderDetailSummary(detail);
      const questions = Array.isArray(detail.questions) ? detail.questions : [];
      els.detailQuestions.innerHTML = questions.length
        ? questions.map(questionRowHtml).join("")
        : '<div class="his-empty"><p class="his-empty-title">这份练习没有题目记录～</p></div>';
    } catch (err) {
      els.detailQuestions.innerHTML =
        '<div class="his-empty"><p class="his-empty-title">明细加载失败啦～</p>' +
        "<p class=\"his-empty-tip\">" + esc(err && err.message ? err.message : "请稍后重试") + "</p></div>";
      CS.toast.error(err && err.message ? err.message : "加载练习明细失败");
    } finally {
      detailLoading = false;
    }
  }

  /* ---------------- 显示/刷新策略 ---------------- */

  /** 页面显示时：缓存脏 → 全量重拉；否则先渲染缓存再后台静默刷新 */
  function onShown() {
    buildSkeleton();
    showListView();

    if (CS.state.historyCacheDirty) {
      page = 1;
      CS.state.historyCache = null;
      CS.state.historyCacheDirty = false;
      loadPage(page);
      return;
    }

    const cache = CS.state.historyCache;
    if (cache && Array.isArray(cache.items) && cache.items.length > 0) {
      page = Number(cache.page) || 1;
      renderList(cache);
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
    const host = $("page-history");
    if (!host || host.dataset.inited === "1") {
      return;
    }
    host.dataset.inited = "1";
    buildSkeleton();

    els.listView = $("history-list-view");
    els.detailView = $("history-detail-view");
    els.list = $("history-list");
    els.pager = $("history-pager");
    els.pageinfo = $("history-pageinfo");
    els.prev = $("history-prev");
    els.next = $("history-next");
    els.clearRow = $("history-clear-row");
    els.clearBtn = $("history-clear");
    els.detailSummary = $("history-detail-summary");
    els.detailQuestions = $("history-detail-questions");

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
    reload: function () {
      page = 1;
      return loadPage(1);
    }
  };
})();
