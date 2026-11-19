"use strict";

/* 错题本前端单元测试（Node 内置 node:test，无第三方依赖）。
 *
 * 运行：node --test tests/js/wrongbook.test.js
 *
 * 用极简 DOM / 桥接桩驱动 web/js/pages/wrongbook.js，重点保护：
 *   - 分页大小来自 get_settings 的 per_page，回退逻辑正确
 *   - 翻页 / 筛选 / 排序携带正确参数
 *   - 单条删除与清空均为两步确认，且传入正确 id
 *   - 重新练习使用筛选总数而非当前页条目数
 */

const { test, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");

const SCRIPT = "../../web/js/pages/wrongbook.js";
const realSetImmediate = setImmediate;
let realSetTimeout;
let realClearTimeout;
let timers;
let harness;

function makeEl(id) {
  const listeners = {};
  const classes = new Set();
  return {
    id: id,
    dataset: {},
    innerHTML: "",
    textContent: "",
    value: "",
    disabled: false,
    listeners: listeners,
    classList: {
      add: function () {
        for (const name of arguments) { classes.add(name); }
      },
      remove: function () {
        for (const name of arguments) { classes.delete(name); }
      },
      toggle: function (name, force) {
        const on = force === undefined ? !classes.has(name) : !!force;
        if (on) { classes.add(name); } else { classes.delete(name); }
        return on;
      },
      contains: function (name) { return classes.has(name); }
    },
    addEventListener: function (type, fn) {
      (listeners[type] || (listeners[type] = [])).push(fn);
    },
    querySelectorAll: function () { return []; }
  };
}

function fire(el, type, event) {
  const handlers = el.listeners[type] || [];
  handlers.forEach(function (fn) {
    fn.call(el, Object.assign({ stopPropagation: function () {} }, event || {}));
  });
}

function makeSortButtons() {
  const first = makeEl("sort-count");
  first.dataset.order = "wrong_count";
  first.classList.add("is-active");
  const second = makeEl("sort-time");
  second.dataset.order = "last_wrong_at";
  return [first, second];
}

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

async function flush() {
  for (let i = 0; i < 8; i++) {
    await new Promise(function (resolve) { realSetImmediate(resolve); });
  }
}

beforeEach(function () {
  timers = [];
  realSetTimeout = global.setTimeout;
  realClearTimeout = global.clearTimeout;
  global.setTimeout = function (fn) { timers.push(fn); return timers.length - 1; };
  global.clearTimeout = function () {};

  const elements = {};
  function byId(id) {
    if (!elements[id]) { elements[id] = makeEl(id); }
    return elements[id];
  }
  const host = byId("page-wrongbook");
  const sortBtns = makeSortButtons();
  host.querySelectorAll = function (selector) {
    return selector === ".sort-btn" ? sortBtns : [];
  };
  const list = makeEl("wrong-list");
  const harnessRef = { deleteSpans: null };
  Object.defineProperty(list, "innerHTML", {
    get: function () { return list._html || ""; },
    set: function (value) {
      list._html = String(value);
      harnessRef.deleteSpans = Array.from(
        list._html.matchAll(/data-id="(\d+)"/g)
      ).map(function (m) {
        const span = makeEl("delete-" + m[1]);
        span.dataset.id = m[1];
        span.textContent = "删除";
        return span;
      });
    }
  });
  list.querySelectorAll = function (selector) {
    return selector === ".his-act-del" ? (harnessRef.deleteSpans || []) : [];
  };
  elements["wrong-list"] = list;

  harness = {
    elements: elements,
    host: host,
    sortBtns: sortBtns,
    calls: [],
    responses: {
      get_settings: async function () { return { per_page: 5 }; },
      list_wrong_book_page: async function (payload) {
        return pageResponse(12, payload.page_size, payload.page, 101);
      },
      delete_wrong_book_entry: async function () { return { deleted: true }; },
      clear_wrong_book: async function () { return { deleted: 11 }; },
      create_practice_from_wrong_book: async function () {
        return {
          session_id: "s1", questions: [], total_count: 12, per_page: 5,
          total_pages: 3, category: "add", range_n: 20
        };
      }
    },
    deleteSpans: function () { return harnessRef.deleteSpans || []; }
  };

  global.document = { getElementById: byId };
  global.window = global;
  global.MutationObserver = function (callback) {
    harness.observer = callback;
    this.observe = function () {};
  };
  global.CS = {
    state: {},
    api: {
      callBridge: async function (method, payload) {
        harness.calls.push({ method: method, payload: payload });
        const handler = harness.responses[method];
        if (!handler) { throw new Error("未预期的桥接方法 " + method); }
        return handler(payload);
      }
    },
    router: { showPage: function () {} },
    toast: { success: function () {}, error: function () {}, info: function () {} }
  };

  delete require.cache[require.resolve(SCRIPT)];
  require(SCRIPT);
});

afterEach(function () {
  global.setTimeout = realSetTimeout;
  global.clearTimeout = realClearTimeout;
  delete global.document;
  delete global.MutationObserver;
  delete global.CS;
  delete global.window;
});

async function showPage() {
  harness.host.classList.add("active");
  harness.observer();
  await flush();
}

test("分页大小来自设置页 per_page，渲染总页数与删除按钮", async function () {
  await showPage();

  const settingsCall = harness.calls.find(function (c) { return c.method === "get_settings"; });
  assert.ok(settingsCall, "应读取持久化设置");
  const listCalls = harness.calls.filter(function (c) {
    return c.method === "list_wrong_book_page";
  });
  assert.equal(listCalls.length, 1);
  assert.deepEqual(listCalls[0].payload, {
    order_by: "wrong_count", page: 1, page_size: 5
  });

  assert.match(harness.elements["wrong-pageinfo"].textContent, /第 1 \/ 3 页 · 共 12 条/);
  assert.equal(harness.deleteSpans().length, 5);
  assert.equal(harness.elements["wrong-pager"].classList.contains("hidden"), false);
  assert.equal(harness.elements["wrong-clear-row"].classList.contains("hidden"), false);
});

test("设置读取失败时回退到当前会话配置的 per_page", async function () {
  global.CS.state.config = { per_page: 20 };
  harness.responses.get_settings = async function () { throw new Error("读取失败"); };
  await showPage();

  const listCall = harness.calls.find(function (c) {
    return c.method === "list_wrong_book_page";
  });
  assert.equal(listCall.payload.page_size, 20);
});

test("上一页/下一页与筛选、排序均携带正确参数", async function () {
  await showPage();

  fire(harness.elements["wrong-next"], "click");
  await flush();
  let calls = harness.calls.filter(function (c) {
    return c.method === "list_wrong_book_page";
  });
  assert.equal(calls[calls.length - 1].payload.page, 2);

  fire(harness.elements["wrong-prev"], "click");
  await flush();
  calls = harness.calls.filter(function (c) {
    return c.method === "list_wrong_book_page";
  });
  assert.equal(calls[calls.length - 1].payload.page, 1);

  harness.elements["wrong-category"].value = "add";
  fire(harness.elements["wrong-category"], "change");
  await flush();
  calls = harness.calls.filter(function (c) {
    return c.method === "list_wrong_book_page";
  });
  assert.equal(calls[calls.length - 1].payload.page, 1);
  assert.equal(calls[calls.length - 1].payload.category, "add");

  fire(harness.sortBtns[1], "click");
  await flush();
  calls = harness.calls.filter(function (c) {
    return c.method === "list_wrong_book_page";
  });
  assert.equal(calls[calls.length - 1].payload.order_by, "last_wrong_at");
  assert.equal(calls[calls.length - 1].payload.page, 1);
});

test("单条删除需两次确认，并携带被点条目的 id", async function () {
  await showPage();
  const span = harness.deleteSpans()[0];
  const id = Number(span.dataset.id);
  assert.equal(id, 101);

  fire(span, "click");
  assert.equal(span.textContent, "确认删除");
  assert.equal(harness.calls.filter(function (c) {
    return c.method === "delete_wrong_book_entry";
  }).length, 0, "首次点击只进入确认态");

  fire(span, "click");
  await flush();
  const calls = harness.calls.filter(function (c) {
    return c.method === "delete_wrong_book_entry";
  });
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].payload, { id: id });
});

test("清空错题本需两次确认，成功后回到第一页", async function () {
  await showPage();
  const btn = harness.elements["wrong-clear"];

  fire(btn, "click");
  assert.equal(btn.textContent, "再点一次确认清空");
  assert.equal(harness.calls.filter(function (c) {
    return c.method === "clear_wrong_book";
  }).length, 0);

  fire(btn, "click");
  await flush();
  assert.equal(harness.calls.filter(function (c) {
    return c.method === "clear_wrong_book";
  }).length, 1);
  const lastList = harness.calls.filter(function (c) {
    return c.method === "list_wrong_book_page";
  }).pop();
  assert.equal(lastList.payload.page, 1);
});

test("重新练习使用设置页页大小与筛选总数，而非当前页条目数", async function () {
  await showPage();
  assert.equal(harness.deleteSpans().length, 5, "当前页只有 5 条");

  fire(harness.elements["wrong-retry"], "click");
  await flush();
  const call = harness.calls.find(function (c) {
    return c.method === "create_practice_from_wrong_book";
  });
  assert.ok(call);
  assert.equal(call.payload.per_page, 5);
  assert.equal(call.payload.count, 12);
});
