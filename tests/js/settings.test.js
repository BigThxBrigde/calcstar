"use strict";

/* 设置页「算式形式」收集逻辑单元测试（Node 内置 node:test，无依赖）。
 *
 * 运行：node --test tests/js/settings.test.js
 *
 * 保护：4 目、自定义 2~10 目、随机 2/3/4 与三种填空位置在前端收集时
 * 不被压回旧取值（历史上非 any 一律变成 last）。
 */

const { test, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");

const SCRIPT = "../../web/js/pages/settings.js";

function makeEl(id) {
  const listeners = {};
  const classes = new Set();
  return {
    id: id,
    dataset: {},
    innerHTML: "",
    textContent: "",
    value: "",
    checked: false,
    disabled: false,
    listeners: listeners,
    classList: {
      add: function (n) { classes.add(n); },
      remove: function (n) { classes.delete(n); },
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
    dispatchEvent: function () {},
    focus: function () {},
    querySelector: function (sel) { return document.querySelector(sel); }
  };
}

let harness;

beforeEach(function () {
  harness = {
    radios: {
      category: "add",
      range: "10",
      count: "20",
      duration: "none",
      "per-page": "10",
      "operand-count": "2",
      "blank-position": "last"
    },
    ids: {}
  };

  function checkedValue(name) {
    const match = /name="([^"]+)"/.exec(name);
    return match ? harness.radios[match[1]] : undefined;
  }

  global.document = {
    getElementById: function (id) {
      if (!harness.ids[id]) { harness.ids[id] = makeEl(id); }
      return harness.ids[id];
    },
    querySelector: function (selector) {
      if (selector.indexOf(":checked") > -1) {
        const value = checkedValue(selector);
        return value === undefined ? null : { value: value };
      }
      return makeEl(selector);
    },
    querySelectorAll: function () { return []; }
  };
  global.window = global;
  global.Event = function () {};
  global.CS = {
    state: {},
    api: {
      callBridge: async function (method) {
        if (method === "get_settings") { return {}; }
        return {};
      },
      ready: async function () {}
    },
    router: { showPage: function () {} },
    toast: { success: function () {}, error: function () {}, info: function () {} }
  };

  delete require.cache[require.resolve(SCRIPT)];
  require(SCRIPT);
});

afterEach(function () {
  delete global.document;
  delete global.Event;
  delete global.CS;
  delete global.window;
});

test("自定义算式个数与固定在算式中均原样收集", function () {
  harness.radios["operand-count"] = "custom";
  harness.radios["blank-position"] = "middle";
  document.getElementById("custom-operand").value = "7";

  const result = global.CS.pages.settings.collectConfig();
  assert.equal(result.ok, true);
  assert.equal(result.config.operand_count, 7);
  assert.equal(result.config.blank_position, "middle");
});

test("固定四目与两种随机均原样收集", function () {
  harness.radios["operand-count"] = "4";
  harness.radios["blank-position"] = "last";
  let result = global.CS.pages.settings.collectConfig();
  assert.equal(result.config.operand_count, 4);
  assert.equal(result.config.blank_position, "last");

  harness.radios["operand-count"] = "random";
  harness.radios["blank-position"] = "any";
  result = global.CS.pages.settings.collectConfig();
  assert.equal(result.config.operand_count, "random");
  assert.equal(result.config.blank_position, "any");
});

test("自定义算式个数超出 2~10 时给出错误", function () {
  harness.radios["operand-count"] = "custom";
  document.getElementById("custom-operand").value = "11";

  const result = global.CS.pages.settings.collectConfig();
  assert.equal(result.ok, false);
  assert.match(result.message, /2~10/);
});
