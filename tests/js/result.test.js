"use strict";

/* 结果页订正分页单元测试（Node 内置 node:test，无第三方依赖）。
 *
 * 运行：node --test tests/js/result.test.js
 *
 * 保护：订正列表只取本局 wrong_answers、按设置页 per_page 分页、
 * 翻页与跨页答案保留、提交时汇总全部本局错题。
 */

const { test, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");

const SCRIPT = "../../web/js/pages/result.js";

function makeEl(id) {
  const listeners = {};
  const classes = new Set();
  const el = {
    id: id,
    dataset: {},
    textContent: "",
    value: "",
    disabled: false,
    children: [],
    listeners: listeners,
    classList: {
      add: function () { for (const n of arguments) { classes.add(n); } },
      remove: function () { for (const n of arguments) { classes.delete(n); } },
      toggle: function (n, force) {
        const on = force === undefined ? !classes.has(n) : !!force;
        if (on) { classes.add(n); } else { classes.delete(n); }
        return on;
      },
      contains: function (n) { return classes.has(n); }
    },
    addEventListener: function (type, fn) {
      (listeners[type] || (listeners[type] = [])).push(fn);
    },
    appendChild: function (child) { el.children.push(child); return child; },
    setAttribute: function (key, value) { el[key] = value; },
    querySelector: function (sel) { return document.querySelector(sel); },
    querySelectorAll: function (sel) { return document.querySelectorAll(sel); },
    focus: function () {},
    select: function () {}
  };
  let html = "";
  Object.defineProperty(el, "innerHTML", {
    get: function () { return html; },
    set: function (value) { html = String(value); el.children.length = 0; }
  });
  return el;
}

function fire(el, type, event) {
  (el.listeners[type] || []).forEach(function (fn) {
    fn.call(el, Object.assign({ preventDefault: function () {} }, event || {}));
  });
}

let harness;

beforeEach(function () {
  const byId = {};
  const bySelector = {};
  function getEl(id) {
    if (!byId[id]) { byId[id] = makeEl(id); }
    return byId[id];
  }
  function query(sel) {
    if (!bySelector[sel]) { bySelector[sel] = makeEl(sel); }
    return bySelector[sel];
  }
  const statValues = [makeEl("stat0"), makeEl("stat1"), makeEl("stat2")];

  global.document = {
    getElementById: getEl,
    querySelector: query,
    querySelectorAll: function (sel) {
      return sel.indexOf("stat-chip") > -1 ? statValues : [];
    },
    createElement: function () { return makeEl("created"); },
    createDocumentFragment: function () { return makeEl("fragment"); }
  };
  global.window = global;
  global.MutationObserver = function () { this.observe = function () {}; };

  harness = {
    byId: byId,
    query: query,
    calls: [],
    settings: { per_page: 5 },
    correctionResponse: {
      correction_round: 1,
      all_correct: false,
      passed: false,
      wrong_answers: []
    }
  };
  global.CS = {
    state: {},
    api: {
      callBridge: async function (method, payload) {
        harness.calls.push({ method: method, payload: payload });
        if (method === "get_settings") { return harness.settings; }
        if (method === "submit_correction") { return harness.correctionResponse; }
        throw new Error("未预期的桥接方法 " + method);
      },
      ready: async function () {}
    },
    router: { showPage: function () {} },
    toast: { success: function () {}, error: function () {}, info: function () {} }
  };

  const wrong = [];
  for (let i = 0; i < 12; i++) {
    wrong.push({
      seq: i, expression: i + " + 1 = ( )", answer: i + 1, user_answer: 0
    });
  }
  global.CS.state.practice = {
    sessionId: "s1",
    result: {
      score: 0, correct_count: 0, total_count: 12, passed: false,
      wrong_answers: wrong
    },
    elapsedSeconds: 30
  };
  getEl("page-result").classList.add("active");

  delete require.cache[require.resolve(SCRIPT)];
  require(SCRIPT);
});

afterEach(function () {
  delete global.document;
  delete global.MutationObserver;
  delete global.CS;
  delete global.window;
});

async function activate() {
  await global.CS.pages.result.activate();
}

function currentRows() {
  const list = harness.query(".wrong-list");
  return list.children[0] ? list.children[0].children : [];
}

function inputSeqs() {
  return currentRows().map(function (row) {
    return Number(row.children[4].dataset.seq);
  });
}

test("订正列表按设置页 per_page 分页，仅展示本局错题的一页", async function () {
  await activate();
  assert.equal(
    harness.byId["correction-pageinfo"].textContent, "第 1 / 3 页 · 共 12 题"
  );
  assert.equal(harness.byId["correction-pager"].classList.contains("hidden"), false);
  assert.deepEqual(inputSeqs(), [0, 1, 2, 3, 4]);
});

test("翻页后序号连续，且上一页输入内容保留", async function () {
  await activate();
  const firstInput = currentRows()[0].children[4];
  firstInput.value = "7";
  fire(firstInput, "input");

  fire(harness.byId["correction-next"], "click");
  assert.equal(
    harness.byId["correction-pageinfo"].textContent, "第 2 / 3 页 · 共 12 题"
  );
  assert.deepEqual(inputSeqs(), [5, 6, 7, 8, 9]);

  fire(harness.byId["correction-prev"], "click");
  assert.deepEqual(inputSeqs(), [0, 1, 2, 3, 4]);
  assert.equal(currentRows()[0].children[4].value, "7");
});

test("提交订正汇总全部本局错题，而非仅当前页", async function () {
  await activate();
  // 跨三页逐题填写，验证末页填写的内容也会进入提交载荷
  for (let p = 0; p < 3; p++) {
    currentRows().forEach(function (row) {
      const input = row.children[4];
      input.value = "1";
      fire(input, "input");
    });
    if (p < 2) {
      fire(harness.byId["correction-next"], "click");
    }
  }

  await global.CS.pages.result.submitCorrection();
  const call = harness.calls.find(function (c) {
    return c.method === "submit_correction";
  });
  assert.ok(call);
  assert.equal(call.payload.session_id, "s1");
  // 12 题分布三页，全部进入提交载荷，不会因分页而漏掉
  assert.equal(Object.keys(call.payload.corrections).length, 12);
  assert.equal(call.payload.corrections["0"], 1);
});
