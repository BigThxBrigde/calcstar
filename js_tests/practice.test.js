"use strict";

/* 练习做题页单元测试（Jest + jsdom）。 */

const { reset, load, stubApi, stubShell, fire } = require("./support");

let host;
let calls;
let intervalFns;
let realSetInterval;
let realClearInterval;
let nowSpy;

const session = {
  session_id: "s1",
  questions: [
    { seq: 0, expression: "1 + 2 = ( )" },
    { seq: 1, expression: "3 + 4 = ( )" },
    { seq: 2, expression: "5 + 6 = ( )" }
  ],
  total_count: 3,
  per_page: 2,
  total_pages: 2,
  duration_seconds: null
};

async function settle() {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
  }
}

beforeEach(function () {
  reset();
  stubShell();
  calls = stubApi({
    submit_practice: function () {
      return { score: 100, correct_count: 3, total_count: 3, passed: true, wrong_answers: [] };
    }
  });
  window.CS.state = {
    currentSession: JSON.parse(JSON.stringify(session)),
    config: { per_page: 2 },
    answers: {},
    startedAt: 1000
  };

  intervalFns = [];
  realSetInterval = global.setInterval;
  realClearInterval = global.clearInterval;
  global.setInterval = function (fn) { intervalFns.push(fn); return intervalFns.length; };
  global.clearInterval = function () {};
  nowSpy = jest.spyOn(Date, "now").mockReturnValue(1000);

  host = document.createElement("div");
  host.id = "page-practice";
  host.className = "active";
  document.body.appendChild(host);

  load("pages/practice.js");
  window.CS.pages.practice.activate();
  return settle();
});

afterEach(function () {
  global.setInterval = realSetInterval;
  global.clearInterval = realClearInterval;
  nowSpy.mockRestore();
});

function inputs() {
  return document.querySelectorAll(".q-input");
}

test("激活后按当前会话渲染题目、分页与进度", function () {
  expect(inputs()).toHaveLength(2);
  expect(document.querySelectorAll(".q-seq")[0].textContent).toBe("1");
  expect(document.querySelector(".q-expression").textContent).toBe("1 + 2 = ( )");
  expect(document.querySelector(".page-indicator").textContent).toBe("1 / 2");
  expect(document.querySelector(".practice-progress").textContent)
    .toBe("第 1 / 2 页 · 共 3 题");
  expect(document.querySelector(".page-prev").disabled).toBe(true);
  expect(document.querySelector(".page-next").disabled).toBe(false);
  expect(document.querySelector(".timer-text").textContent).toBe("00:00");
  expect(intervalFns).toHaveLength(1);
});

test("输入实时清洗并写入共享作答表", function () {
  const input = inputs()[0];
  input.value = "-0012a";
  fire(input, "input");

  expect(input.value).toBe("-12");
  expect(window.CS.state.answers[0]).toBe("-12");
  expect(input.closest(".question-card").classList.contains("is-answered")).toBe(true);

  input.value = "-";
  fire(input, "input");
  expect(window.CS.state.answers[0]).toBe("-");
  expect(input.closest(".question-card").classList.contains("is-answered")).toBe(false);
});

test("翻页前提醒未作答题号并切换到下一页", function () {
  fire(document.querySelector(".page-next"), "click");

  expect(window.CS.toast.info).toHaveBeenCalledWith("第 1、2 题还没写答案哦！");
  expect(document.querySelector(".page-indicator").textContent).toBe("2 / 2");
  expect(document.querySelector(".page-next").disabled).toBe(true);
  expect(inputs()).toHaveLength(1);
  expect(inputs()[0].dataset.seq).toBe("2");
});

test("提交时收集全卷作答（未作答传 null）并写入结果状态", async function () {
  window.CS.state.answers = { 0: "3", 1: "004", 2: "-" };
  nowSpy.mockReturnValue(7000);

  fire(document.querySelector(".submit-btn"), "click");
  await settle();

  const submitCall = calls.find(function (c) { return c.method === "submit_practice"; });
  expect(submitCall).toBeDefined();
  expect(submitCall.payload).toEqual({
    session_id: "s1",
    answers: { "0": 3, "1": 4, "2": null },
    duration_seconds: 6
  });
  expect(window.CS.toast.info).toHaveBeenCalledWith("还有 1 题没写答案哦，会按未作答提交");
  expect(window.CS.state.practice).toMatchObject({
    sessionId: "s1", elapsedSeconds: 6, timedOut: false
  });
  expect(window.CS.router.showPage).toHaveBeenCalledWith("page-result");
  expect(document.querySelector(".submit-btn").disabled).toBe(false);
  expect(document.querySelector(".btn-label").textContent).toBe("提交练习");
});

test("限时到点自动提交并标记 timedOut", async function () {
  const timed = JSON.parse(JSON.stringify(session));
  timed.duration_seconds = 60;
  window.CS.state.currentSession = timed;
  window.CS.pages.practice.resetSession();
  window.CS.pages.practice.activate();
  await settle();

  nowSpy.mockReturnValue(61000);
  intervalFns[intervalFns.length - 1]();
  await settle();

  expect(document.querySelector(".timer-text").textContent).toBe("00:00");
  expect(window.CS.toast.info).toHaveBeenCalledWith("时间到啦，自动提交咯！");
  expect(window.CS.state.practice.timedOut).toBe(true);
  expect(calls.filter(function (c) { return c.method === "submit_practice"; }))
    .toHaveLength(1);
});

test("倒计时进入最后 60 秒时显示告急样式", function () {
  const timed = JSON.parse(JSON.stringify(session));
  timed.duration_seconds = 120;
  window.CS.state.currentSession = timed;
  window.CS.pages.practice.resetSession();
  window.CS.pages.practice.activate();

  nowSpy.mockReturnValue(71000);
  intervalFns[intervalFns.length - 1]();

  expect(document.querySelector(".timer-text").textContent).toBe("00:50");
  expect(document.querySelector(".timer-pill").classList.contains("is-urgent")).toBe(true);
});

test("没有当前会话时展示空状态并停止计时", function () {
  window.CS.state.currentSession = null;
  window.CS.pages.practice.resetSession();
  window.CS.pages.practice.activate();

  expect(document.querySelector(".empty-hint").classList.contains("hidden")).toBe(false);
  expect(document.querySelector(".practice-body").classList.contains("hidden")).toBe(true);
  expect(document.querySelector(".practice-topbar").classList.contains("hidden")).toBe(true);
});

test("resetSession 后再次激活按新练习重置页码", function () {
  fire(document.querySelector(".page-next"), "click");
  expect(document.querySelector(".page-indicator").textContent).toBe("2 / 2");

  window.CS.pages.practice.resetSession();
  window.CS.pages.practice.activate();

  expect(document.querySelector(".page-indicator").textContent).toBe("1 / 2");
});
