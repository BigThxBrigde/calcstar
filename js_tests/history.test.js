"use strict";

/* 历史成绩页单元测试（Jest + jsdom）。 */

const { reset, load, stubApi, stubShell, fire } = require("./support");

let host;
let calls;
let timers;
let realSetTimeout;
let realClearTimeout;

function historyResponse(total, page, pageSize) {
  const count = Math.min(pageSize, Math.max(0, total - (page - 1) * pageSize));
  const items = [];
  for (let i = 0; i < count; i++) {
    const id = (page - 1) * pageSize + i + 1;
    items.push({
      id: id,
      category: "add",
      range_n: 20,
      count: 10,
      started_at: "2026-11-19T10:30:00",
      finished_at: "2026-11-19T10:31:23",
      duration_seconds: 83,
      correct_count: 9,
      total_count: 10,
      score: 90,
      status: "submitted",
      passed: 1
    });
  }
  return { items: items, total: total, page: page, page_size: pageSize };
}

async function settle() {
  for (let i = 0; i < 12; i++) {
    await Promise.resolve();
  }
}

beforeEach(function () {
  reset();
  stubShell();
  window.CS.state = {};
  window.CS.pages = { practice: { resetSession: jest.fn() } };

  calls = stubApi({
    list_history: function (payload) {
      return historyResponse(12, payload.page, payload.page_size);
    },
    get_session_detail: function (payload) {
      return Object.assign(historyResponse(1, 1, 1).items[0], {
        questions: [
          { seq: 0, expression: "<img src=x>", answer: 3, user_answer: 3, is_correct: 1 },
          { seq: 1, expression: "4 - 1 = ( )", answer: 3, user_answer: null, is_correct: null }
        ]
      });
    },
    export_report_pdf: function () { return { path: "D:/reports/s1.pdf" }; },
    reset_practice: function () {
      return { session_id: "s1", questions: [{ seq: 0, expression: "1 + 1 = ( )" }] };
    },
    delete_session: function () { return { deleted: 1 }; },
    clear_history: function () { return { deleted: 12 }; }
  });

  timers = [];
  realSetTimeout = global.setTimeout;
  realClearTimeout = global.clearTimeout;
  global.setTimeout = function (fn) { timers.push(fn); return timers.length - 1; };
  global.clearTimeout = function () {};

  host = document.createElement("div");
  host.id = "page-history";
  host.className = "active";
  document.body.appendChild(host);

  load("pages/history.js");
  return settle();
});

afterEach(function () {
  global.setTimeout = realSetTimeout;
  global.clearTimeout = realClearTimeout;
});

function listCalls() {
  return calls.filter(function (c) { return c.method === "list_history"; });
}

test("列表渲染成绩行、分页状态与缓存", async function () {
  expect(listCalls()).toHaveLength(1);
  expect(listCalls()[0].payload).toEqual({ page: 1, page_size: 10 });
  expect(document.querySelectorAll(".his-row")).toHaveLength(10);
  expect(document.getElementById("history-pageinfo").textContent)
    .toBe("第 1 / 2 页 · 共 12 条");
  expect(document.getElementById("history-prev").disabled).toBe(true);
  expect(document.getElementById("history-next").disabled).toBe(false);
  expect(document.querySelector(".his-badge-pass")).not.toBeNull();
  expect(window.CS.state.historyCache.total).toBe(12);
  expect(window.CS.state.historyCacheDirty).toBe(false);
});

test("空历史展示空状态并隐藏分页与清空入口", async function () {
  window.CS.api.callBridge.mockImplementation(function (method, payload) {
    if (method === "list_history") {
      return Promise.resolve({ items: [], total: 0, page: payload.page, page_size: 10 });
    }
    return Promise.resolve({});
  });
  window.CS.pages.history.reload();
  await settle();

  expect(document.querySelector(".his-empty-title").textContent).toContain("空空如也");
  expect(document.getElementById("history-pager").classList.contains("hidden")).toBe(true);
  expect(document.getElementById("history-clear-row").classList.contains("hidden")).toBe(true);
});

test("越界页会回退到最后一页", async function () {
  window.CS.api.callBridge.mockImplementation(function (method, payload) {
    calls.push({ method: method, payload: payload });
    if (method === "list_history") {
      if (payload.page === 3) {
        return Promise.resolve({ items: [], total: 12, page: 3, page_size: 10 });
      }
      return Promise.resolve(historyResponse(12, payload.page, payload.page_size));
    }
    return Promise.resolve({});
  });

  fire(document.getElementById("history-next"), "click");
  await settle();
  fire(document.getElementById("history-next"), "click");
  await settle();

  const pages = listCalls().map(function (c) { return c.payload.page; });
  expect(pages.slice(-2)).toEqual([3, 2]);
  expect(document.getElementById("history-pageinfo").textContent)
    .toBe("第 2 / 2 页 · 共 12 条");
});

test("点击成绩行打开明细，返回按钮回到列表", async function () {
  fire(document.querySelectorAll(".his-row")[0], "click");
  await settle();

  expect(calls.filter(function (c) { return c.method === "get_session_detail"; })[0].payload)
    .toEqual({ session_id: 1 });
  expect(document.getElementById("history-list-view").classList.contains("hidden")).toBe(true);
  expect(document.getElementById("history-detail-view").classList.contains("hidden")).toBe(false);
  expect(document.querySelectorAll(".his-q")).toHaveLength(2);
  expect(document.querySelector(".his-q-expr").textContent).toBe("<img src=x>");
  expect(document.querySelector(".his-q-expr img")).toBeNull();
  expect(document.querySelectorAll(".his-q-mark")[1].textContent).toBe("—");

  fire(document.getElementById("history-detail-back"), "click");
  expect(document.getElementById("history-detail-view").classList.contains("hidden")).toBe(true);
  expect(document.getElementById("history-list-view").classList.contains("hidden")).toBe(false);
});

test("导出与重做分别调用后端并更新界面/共享状态", async function () {
  const rows = document.querySelectorAll(".his-row");
  fire(rows[0].querySelector('[data-act="export"]'), "click");
  await settle();

  expect(calls.filter(function (c) { return c.method === "export_report_pdf"; })[0].payload)
    .toEqual({ session_id: 1 });
  expect(window.CS.mask.show).toHaveBeenCalledWith("正在生成成绩单…");
  expect(window.CS.mask.hide).toHaveBeenCalled();
  expect(window.CS.toast.success).toHaveBeenCalledWith("成绩单已保存：D:/reports/s1.pdf");

  fire(document.querySelectorAll(".his-row")[1].querySelector('[data-act="redo"]'), "click");
  await settle();

  expect(calls.filter(function (c) { return c.method === "reset_practice"; })[0].payload)
    .toEqual({ session_id: 2 });
  expect(window.CS.pages.practice.resetSession).toHaveBeenCalled();
  expect(window.CS.state.currentSession.session_id).toBe("s1");
  expect(window.CS.state.answers).toEqual({});
  expect(window.CS.router.showPage).toHaveBeenCalledWith("page-practice");
});

test("行级删除需两次确认，成功后刷新当前页", async function () {
  const span = document.querySelectorAll(".his-row")[0].querySelector('[data-act="del"]');
  fire(span, "click");
  expect(span.textContent).toBe("确认删除");
  expect(calls.filter(function (c) { return c.method === "delete_session"; })).toHaveLength(0);

  fire(span, "click");
  await settle();

  expect(calls.filter(function (c) { return c.method === "delete_session"; })[0].payload)
    .toEqual({ session_id: 1 });
  expect(window.CS.toast.success).toHaveBeenCalledWith("已删除该次练习记录，错题本保留");
  expect(listCalls().length).toBeGreaterThan(1);
});

test("清空历史需两次确认，成功后回到第一页", async function () {
  const btn = document.getElementById("history-clear");
  fire(btn, "click");
  expect(btn.textContent).toBe("再点一次确认清空");
  expect(calls.filter(function (c) { return c.method === "clear_history"; })).toHaveLength(0);

  fire(btn, "click");
  await settle();

  expect(window.CS.toast.success).toHaveBeenCalledWith("已清空 12 次练习记录，错题本保留");
  expect(listCalls().pop().payload.page).toBe(1);
});

test("缓存脏时重新显示会丢弃缓存并全量重拉", async function () {
  window.CS.state.historyCacheDirty = true;
  const before = listCalls().length;

  host.classList.remove("active");
  await settle();
  host.classList.add("active");
  await settle();

  expect(listCalls().length).toBeGreaterThan(before);
  expect(window.CS.state.historyCacheDirty).toBe(false);
  expect(window.CS.state.historyCache.page).toBe(1);
});

test("缓存有效时先渲染旧数据，随后静默刷新", async function () {
  window.CS.state.historyCache = {
    page: 1, pageSize: 10, total: 12,
    items: historyResponse(12, 1, 10).items
  };
  const before = listCalls().length;

  host.classList.remove("active");
  await settle();
  host.classList.add("active");
  await settle();

  expect(listCalls().length).toBe(before, "静默刷新由延时器触发");
  expect(document.querySelectorAll(".his-row")).toHaveLength(10);

  timers[timers.length - 1]();
  await settle();
  expect(listCalls().length).toBe(before + 1);
});
