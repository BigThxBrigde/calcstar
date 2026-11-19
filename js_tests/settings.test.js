"use strict";

/* 设置页单元测试（Jest + jsdom）。 */

const { reset, load, stubApi, stubShell, flush, fire } = require("./support");

let calls;
let savedSettings;

function radio(name, value) {
  return document.querySelector('input[name="' + name + '"][value="' + value + '"]');
}

function check(name, value) {
  document.querySelectorAll('input[name="' + name + '"]').forEach(function (input) {
    input.checked = input.value === String(value);
  });
}

function checkedValue(name) {
  const input = document.querySelector('input[name="' + name + '"]:checked');
  return input ? input.value : null;
}

function buildForm() {
  document.body.innerHTML =
    '<div id="row-parentheses">' +
    '  <input type="checkbox" id="allow-negative">' +
    '  <input type="checkbox" id="with-parentheses">' +
    "</div>" +
    '<input type="text" id="custom-range">' +
    '<div id="row-custom-range"></div>' +
    '<input type="text" id="custom-count">' +
    '<div id="row-custom-count"></div>' +
    '<input type="text" id="custom-duration">' +
    '<div id="row-custom-duration"></div>' +
    '<button id="start-btn"><span class="btn-label">开始练习</span></button>' +
    '<button id="nav-history"></button><button id="nav-wrongbook"></button>' +

    '<input type="radio" name="category" value="add" checked>' +
    '<input type="radio" name="category" value="sub">' +
    '<input type="radio" name="category" value="mixed">' +

    '<input type="radio" name="range" value="20" checked>' +
    '<input type="radio" name="range" value="100">' +
    '<input type="radio" name="range" value="custom">' +
    '<input type="radio" name="count" value="10" checked>' +
    '<input type="radio" name="count" value="50">' +
    '<input type="radio" name="count" value="custom">' +
    '<input type="radio" name="duration" value="none" checked>' +
    '<input type="radio" name="duration" value="3">' +
    '<input type="radio" name="duration" value="custom">' +
    '<input type="radio" name="per-page" value="5" checked>' +
    '<input type="radio" name="per-page" value="10">' +
    '<input type="radio" name="operand-count" value="2" checked>' +
    '<input type="radio" name="operand-count" value="random">' +
    '<input type="radio" name="blank-position" value="last" checked>' +
    '<input type="radio" name="blank-position" value="any">';
}

async function setup(saved) {
  reset();
  stubShell();
  window.CS.state = {};
  savedSettings = saved || {};
  calls = stubApi({
    get_settings: function () { return savedSettings; },
    save_settings: function () { return {}; },
    create_practice: function () {
      return { session_id: "s1", questions: [], per_page: 5 };
    }
  });
  buildForm();
  load("pages/settings.js");
  await flush();
}

beforeEach(function () {
  return setup({});
});

test("默认表单收集为后端约定的 config", function () {
  const result = window.CS.pages.settings.collectConfig();

  expect(result.ok).toBe(true);
  expect(result.config).toEqual({
    category: "add",
    range_n: 20,
    count: 10,
    duration_minutes: null,
    allow_negative: false,
    include_parentheses: false,
    per_page: 5,
    operand_count: 2,
    blank_position: "last"
  });
});

test("自定义数值、限时与四则混合括号开关均可收集", function () {
  check("range", "custom");
  document.getElementById("custom-range").value = " 37 ";
  check("count", "custom");
  document.getElementById("custom-count").value = "25";
  check("duration", "custom");
  document.getElementById("custom-duration").value = "12";
  check("category", "mixed");
  check("per-page", "10");
  check("operand-count", "random");
  check("blank-position", "any");
  document.getElementById("allow-negative").checked = true;
  document.getElementById("with-parentheses").checked = true;

  const result = window.CS.pages.settings.collectConfig();

  expect(result.ok).toBe(true);
  expect(result.config).toMatchObject({
    category: "mixed",
    range_n: 37,
    count: 25,
    duration_minutes: 12,
    allow_negative: true,
    include_parentheses: true,
    per_page: 10,
    operand_count: "random",
    blank_position: "any"
  });
});

test("缺项与越界自定义值给出对应校验提示", function () {
  check("category", "none");
  expect(window.CS.pages.settings.collectConfig())
    .toEqual({ ok: false, message: "请先选择运算类别" });

  check("category", "add");
  check("range", "custom");
  document.getElementById("custom-range").value = "1000";
  expect(window.CS.pages.settings.collectConfig())
    .toEqual({ ok: false, message: "数值范围需为 1~999 之间的整数" });

  check("range", "20");
  check("count", "custom");
  document.getElementById("custom-count").value = "201";
  expect(window.CS.pages.settings.collectConfig())
    .toEqual({ ok: false, message: "题目数量需为 1~200 之间的整数" });

  check("count", "10");
  check("per-page", "none");
  expect(window.CS.pages.settings.collectConfig())
    .toEqual({ ok: false, message: "请选择每页题数" });

  check("per-page", "5");
  check("operand-count", "none");
  expect(window.CS.pages.settings.collectConfig())
    .toEqual({ ok: false, message: "请选择算式目数" });
});

test("开始练习会持久化配置、写入共享状态并跳转练习页", async function () {
  fire(document.getElementById("start-btn"), "click");
  await flush();

  const config = window.CS.pages.settings.collectConfig().config;
  expect(calls.filter(function (c) { return c.method === "save_settings"; })[0].payload)
    .toEqual(config);
  expect(calls.filter(function (c) { return c.method === "create_practice"; })[0].payload)
    .toEqual(config);
  expect(window.CS.state.currentSession.session_id).toBe("s1");
  expect(window.CS.state.config).toEqual(config);
  expect(window.CS.state.answers).toEqual({});
  expect(typeof window.CS.state.startedAt).toBe("number");
  expect(window.CS.router.showPage).toHaveBeenCalledWith("page-practice");
  expect(window.CS.toast.success).toHaveBeenCalledWith("练习已生成，加油哦！");
  expect(document.getElementById("start-btn").disabled).toBe(false);
  expect(document.querySelector(".btn-label").textContent).toBe("开始练习");
});

test("启动时回填持久化设置，包括自定义值与混合括号开关", async function () {
  await setup({
    category: "mixed",
    range_n: 37,
    count: 25,
    duration_minutes: null,
    allow_negative: true,
    include_parentheses: true,
    per_page: 10,
    operand_count: "random",
    blank_position: "any"
  });

  expect(checkedValue("category")).toBe("mixed");
  expect(checkedValue("range")).toBe("custom");
  expect(document.getElementById("custom-range").value).toBe("37");
  expect(checkedValue("duration")).toBe("none");
  expect(checkedValue("per-page")).toBe("10");
  expect(checkedValue("operand-count")).toBe("random");
  expect(checkedValue("blank-position")).toBe("any");
  expect(document.getElementById("with-parentheses").disabled).toBe(false);
  expect(document.getElementById("with-parentheses").checked).toBe(true);
  expect(window.CS.pages.settings.collectConfig().config.range_n).toBe(37);
});

test("切离四则混合时自动关闭并禁用括号开关", function () {
  check("category", "mixed");
  fire(radio("category", "mixed"), "change");
  expect(document.getElementById("with-parentheses").disabled).toBe(false);
  document.getElementById("with-parentheses").checked = true;

  check("category", "add");
  fire(radio("category", "add"), "change");

  expect(document.getElementById("with-parentheses").disabled).toBe(true);
  expect(document.getElementById("with-parentheses").checked).toBe(false);
  expect(document.getElementById("row-parentheses").classList.contains("is-disabled")).toBe(true);
  expect(window.CS.pages.settings.collectConfig().config.include_parentheses).toBe(false);
});

test("首页导航按钮跳转到历史成绩与错题本", function () {
  fire(document.getElementById("nav-history"), "click");
  fire(document.getElementById("nav-wrongbook"), "click");

  expect(window.CS.router.showPage).toHaveBeenNthCalledWith(1, "page-history");
  expect(window.CS.router.showPage).toHaveBeenNthCalledWith(2, "page-wrongbook");
});
