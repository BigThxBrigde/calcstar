"use strict";

/* 错题本页单元测试（Jest + jsdom）。
 *
 * 运行：npm test -- wrongbook.test.js（在本目录内）
 */

const { reset, load, stubApi, stubShell, flush, fire } = require("./support");

let host;
let calls;
let timers;
let realSetTimeout;
let realClearTimeout;

function pageResponse(total, pageSize, page, firstId) {
  const count = Math.min(pageSize, Math.max(0, total - (page - 1) * pageSize));
  const items = [];
  for (let i = 0; i < count; i++) {
    items.push({
      id: firstId + i,
      expression: (i + 1) + " + 2 = ( )",
      answer: i + 3,
      wrong_count: 1,
      last_wrong_at: "2026-11-19T10:00:00"
    });
  }
  return { items: items, total: total, page: page, page_size: pageSize };
}

async function settle() {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
  }
}

beforeEach(function () {
  reset();
  stubShell();
  window.CS.state = {};

  calls = stubApi({
    get_settings: function () { return { per_page: 5 }; },
    list_wrong_book_page: function (payload) {
      return pageResponse(12, payload.page_size, payload.page, 101);
    },
    delete_wrong_book_entry: function () { return { deleted: true }; },
    clear_wrong_book: function () { return { deleted: 11 }; },
    create_practice_from_wrong_book: function () {
      return {
        session_id: "s1", questions: [], total_count: 12, per_page: 5,
        total_pages: 3, category: "add", range_n: 20
      };
    }
  });

  timers = [];
  realSetTimeout = global.setTimeout;
  realClearTimeout = global.clearTimeout;
  global.setTimeout = function (fn) { timers.push(fn); return timers.length - 1; };
  global.clearTimeout = function () {};

  host = document.createElement("div");
  host.id = "page-wrongbook";
  host.className = "active";
  document.body.appendChild(host);

  load("pages/wrongbook.js");
  return settle();
});

afterEach(function () {
  global.setTimeout = realSetTimeout;
  global.clearTimeout = realClearTimeout;
});

function listCalls() {
  return calls.filter(function (c) { return c.method === "list_wrong_book_page"; });
}

function deleteSpans() {
  return document.querySelectorAll("#wrong-list .his-act-del");
}

test("分页大小来自设置页 per_page，渲染总页数与删除按钮", async function () {
  await settle();

  expect(calls.find(function (c) { return c.method === "get_settings"; })).toBeDefined();
  expect(listCalls()).toHaveLength(1);
  expect(listCalls()[0].payload).toEqual({
    order_by: "wrong_count", page: 1, page_size: 5
  });
  expect(document.getElementById("wrong-pageinfo").textContent)
    .toMatch(/第 1 \/ 3 页 · 共 12 条/);
  expect(deleteSpans()).toHaveLength(5);
  expect(document.getElementById("wrong-pager").classList.contains("hidden")).toBe(false);
  expect(document.getElementById("wrong-clear-row").classList.contains("hidden")).toBe(false);
});

test("设置读取失败时回退到当前会话配置的 per_page", async function () {
  window.CS.state.config = { per_page: 20 };
  calls.length = 0;
  window.CS.api.callBridge.mockImplementation(function (method, payload) {
    calls.push({ method: method, payload: payload });
    if (method === "get_settings") {
      return Promise.reject(new Error("读取失败"));
    }
    return Promise.resolve(pageResponse(12, payload.page_size, payload.page, 101));
  });
  host.classList.remove("active");
  await settle();
  host.classList.add("active");
  await settle();

  expect(listCalls().pop().payload.page_size).toBe(20);
});

test("上一页/下一页与筛选、排序均携带正确参数", async function () {
  await settle();

  fire(document.getElementById("wrong-next"), "click");
  await settle();
  expect(listCalls().pop().payload.page).toBe(2);

  fire(document.getElementById("wrong-prev"), "click");
  await settle();
  expect(listCalls().pop().payload.page).toBe(1);

  const category = document.getElementById("wrong-category");
  category.value = "add";
  fire(category, "change");
  await settle();
  expect(listCalls().pop().payload).toMatchObject({ page: 1, category: "add" });

  const sortBtns = host.querySelectorAll(".sort-btn");
  fire(sortBtns[1], "click");
  await settle();
  expect(listCalls().pop().payload).toMatchObject({
    order_by: "last_wrong_at", page: 1
  });
  expect(sortBtns[1].classList.contains("is-active")).toBe(true);
  expect(sortBtns[0].classList.contains("is-active")).toBe(false);
});

test("单条删除需两次确认，并携带被点条目的 id", async function () {
  await settle();
  const span = deleteSpans()[0];

  fire(span, "click");
  expect(span.textContent).toBe("确认删除");
  expect(calls.filter(function (c) { return c.method === "delete_wrong_book_entry"; }))
    .toHaveLength(0);

  fire(span, "click");
  await settle();
  const deleteCalls = calls.filter(function (c) {
    return c.method === "delete_wrong_book_entry";
  });
  expect(deleteCalls).toHaveLength(1);
  expect(deleteCalls[0].payload).toEqual({ id: 101 });
  expect(window.CS.toast.success).toHaveBeenCalledWith("已删除该条错题");
  expect(listCalls().length).toBeGreaterThan(1, "删除后应重新拉取当前页");
});

test("清空错题本需两次确认，成功后回到第一页", async function () {
  await settle();
  const btn = document.getElementById("wrong-clear");

  fire(btn, "click");
  expect(btn.textContent).toBe("再点一次确认清空");
  expect(calls.filter(function (c) { return c.method === "clear_wrong_book"; }))
    .toHaveLength(0);

  fire(btn, "click");
  await settle();
  expect(calls.filter(function (c) { return c.method === "clear_wrong_book"; }))
    .toHaveLength(1);
  expect(listCalls().pop().payload.page).toBe(1);
  expect(window.CS.toast.success).toHaveBeenCalledWith("已清空 11 条错题");
});

test("重新练习使用设置页页大小与筛选总数，而非当前页条目数", async function () {
  await settle();
  expect(deleteSpans()).toHaveLength(5, "当前页只有 5 条");

  fire(document.getElementById("wrong-retry"), "click");
  await settle();
  const call = calls.find(function (c) {
    return c.method === "create_practice_from_wrong_book";
  });
  expect(call).toBeDefined();
  expect(call.payload).toEqual({ per_page: 5, count: 12 });
  expect(window.CS.router.showPage).toHaveBeenCalledWith("page-practice");
  expect(window.CS.state.currentSession.session_id).toBe("s1");
});

test("空结果禁用重新练习并隐藏分页与清空入口", async function () {
  window.CS.api.callBridge.mockImplementation(function (method, payload) {
    if (method === "get_settings") { return Promise.resolve({ per_page: 5 }); }
    if (method === "list_wrong_book_page") {
      return Promise.resolve({ items: [], total: 0, page: 1, page_size: 5 });
    }
    return Promise.resolve({});
  });
  window.CS.pages.wrongbook.reload(1);
  await settle();

  expect(document.getElementById("wrong-pager").classList.contains("hidden")).toBe(true);
  expect(document.getElementById("wrong-clear-row").classList.contains("hidden")).toBe(true);
  expect(document.getElementById("wrong-retry").disabled).toBe(true);
  expect(document.querySelector("#wrong-list .his-empty-title").textContent)
    .toContain("没有错题");
});

test("4 秒未确认时删除按钮自动复位", async function () {
  await settle();
  const span = deleteSpans()[0];
  fire(span, "click");
  expect(span.textContent).toBe("确认删除");

  timers[timers.length - 1]();

  expect(span.textContent).toBe("删除");
  expect(span.classList.contains("is-armed")).toBe(false);
  expect(calls.filter(function (c) { return c.method === "delete_wrong_book_entry"; }))
    .toHaveLength(0);
});

test("列表加载失败时展示错误文案并提示", async function () {
  window.CS.api.callBridge.mockImplementation(function (method) {
    if (method === "get_settings") { return Promise.resolve({ per_page: 5 }); }
    return Promise.reject(new Error("后端离线"));
  });
  window.CS.pages.wrongbook.reload(1);
  await settle();

  expect(document.querySelector("#wrong-list .his-empty-tip").textContent)
    .toBe("后端离线");
  expect(window.CS.toast.error).toHaveBeenCalledWith("后端离线");
});
