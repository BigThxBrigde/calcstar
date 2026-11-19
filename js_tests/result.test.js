"use strict";

/* 结果与订正页单元测试（Jest + jsdom）。 */

const { reset, load, stubApi, stubShell, fire } = require("./support");

let host;
let calls;
let responses;

function practice() {
  return {
    sessionId: "s1",
    result: {
      score: 70,
      correct_count: 7,
      total_count: 10,
      passed: false,
      wrong_answers: [
        { seq: 0, expression: "1 + 1 = ( )", answer: 2, user_answer: 1 },
        { seq: 3, expression: "4 + 1 = ( )", answer: 5, user_answer: 3 }
      ]
    },
    elapsedSeconds: 125,
    timedOut: true
  };
}

async function settle() {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
  }
}

beforeEach(function () {
  reset();
  stubShell();
  responses = {
    get_settings: function () { return { per_page: 10 }; },
    submit_correction: function () {
      return {
        correction_round: 1,
        all_correct: false,
        wrong_answers: [{ seq: 3, expression: "4 + 1 = ( )", answer: 5, user_answer: 3 }]
      };
    },
    export_report: function (payload) {
      return { path: payload.format === "png" ? "D:/reports/s1.png" : "D:/reports/s1.pdf" };
    }
  };
  calls = stubApi(responses);
  window.CS.state = {
    practice: practice(),
    currentSession: { session_id: "s1" },
    historyCache: { items: [1] },
    historyCacheDirty: false,
    wrongBookCache: { items: [2] },
    wrongBookCacheDirty: false
  };

  host = document.createElement("div");
  host.id = "page-result";
  host.className = "active";
  document.body.appendChild(host);

  load("pages/result.js");
});

async function activate() {
  await window.CS.pages.result.activate();
}

function inputs() {
  return document.querySelectorAll(".correction-input");
}

function correctionCalls() {
  return calls.filter(function (c) { return c.method === "submit_correction"; });
}

test("渲染得分、正确率、用时与错题列表，并标记缓存失效", async function () {
  await activate();

  expect(document.querySelector(".score-num").textContent).toBe("70");
  const stats = document.querySelectorAll(".result-stats .stat-chip:not(.is-timeout) .chip-value");
  expect(stats[0].textContent).toBe("70%");
  expect(stats[1].textContent).toBe("7 / 10 题");
  expect(stats[2].textContent).toBe("2分05秒");
  expect(document.querySelector(".stat-chip.is-timeout").classList.contains("hidden")).toBe(false);
  expect(document.querySelector(".result-title").textContent)
    .toBe("答完啦，来把错题订正一下吧！");
  expect(inputs()).toHaveLength(2);
  expect(document.querySelector(".wrong-seq").textContent).toBe("1");
  expect(window.CS.state.historyCacheDirty).toBe(true);
  expect(window.CS.state.wrongBookCacheDirty).toBe(true);
  expect(window.CS.state.historyCache).toBeUndefined();
  expect(window.CS.state.wrongBookCache).toBeUndefined();
});

test("全部答对时展示庆祝态且不渲染订正区", async function () {
  const data = practice();
  data.result.passed = true;
  data.result.wrong_answers = [];
  window.CS.state.practice = data;
  await activate();

  expect(document.querySelector(".result-title").textContent).toBe("太棒啦，全部答对！");
  expect(document.querySelector(".wrong-card").classList.contains("hidden")).toBe(true);
  expect(document.querySelector(".passed-note").classList.contains("hidden")).toBe(false);
  expect(document.querySelector(".home-btn").classList.contains("hidden")).toBe(false);
  expect(inputs()).toHaveLength(0);
});

test("订正输入清洗非法字符，回车跳到下一题", async function () {
  await activate();
  const input = inputs()[0];
  input.value = "-0012a";
  fire(input, "input");

  expect(input.value).toBe("-12");
  expect(input.closest(".wrong-row").classList.contains("is-filled")).toBe(true);

  fire(input, "keydown", { key: "Enter" });
  expect(document.activeElement).toBe(inputs()[1]);
});

test("未填完订正答案时只提示不提交", async function () {
  await activate();
  fire(document.querySelector(".correction-btn"), "click");

  expect(window.CS.toast.info).toHaveBeenCalledWith("还有 2 题没填订正答案哦！");
  expect(correctionCalls()).toHaveLength(0);
});

test("订正先返回剩余错题，全部通过后更新状态为 passed", async function () {
  await activate();
  inputs()[0].value = "2";
  inputs()[1].value = "5";
  fire(inputs()[0], "input");
  fire(inputs()[1], "input");
  fire(document.querySelector(".correction-btn"), "click");
  await settle();

  expect(correctionCalls()[0].payload).toEqual({
    session_id: "s1",
    corrections: { "0": 2, "3": 5 }
  });
  expect(window.CS.state.practice.correctionRound).toBe(1);
  expect(window.CS.state.practice.result.wrong_answers).toHaveLength(1);
  expect(document.querySelector(".round-badge").textContent).toBe("已完成 1 轮订正");
  expect(window.CS.toast.info).toHaveBeenCalledWith("还剩 1 题要再想想哦！");
  expect(document.activeElement).toBe(inputs()[0]);

  responses.submit_correction = function () {
    return { correction_round: 2, all_correct: true, wrong_answers: [] };
  };
  inputs()[0].value = "5";
  fire(inputs()[0], "input");
  fire(document.querySelector(".correction-btn"), "click");
  await settle();

  expect(window.CS.state.practice.result.passed).toBe(true);
  expect(window.CS.state.practice.result.wrong_answers).toEqual([]);
  expect(window.CS.state.practice.correctionRound).toBe(2);
  expect(document.querySelector(".result-title").textContent).toBe("错题全部订正通过！");
  expect(window.CS.toast.success).toHaveBeenCalledWith("订正全部通过，你真棒！");
});

test("导出成绩单覆盖成功、取消与失败三种反馈", async function () {
  await activate();
  const btn = document.querySelector(".export-btn");

  fire(btn, "click");
  await settle();
  expect(calls.filter(function (c) { return c.method === "export_report"; })[0].payload)
    .toEqual({ session_id: "s1", format: "pdf" });
  expect(window.CS.mask.show).toHaveBeenCalledWith("正在生成成绩单…");
  expect(window.CS.mask.hide).toHaveBeenCalled();
  expect(window.CS.toast.success).toHaveBeenCalledWith("成绩单已保存：D:/reports/s1.pdf");

  responses.export_report = function () { return { cancelled: true }; };
  fire(btn, "click");
  await settle();
  expect(window.CS.toast.info).toHaveBeenCalledWith("已取消导出");

  responses.export_report = function () { throw new Error("磁盘已满"); };
  fire(btn, "click");
  await settle();
  expect(window.CS.toast.error).toHaveBeenCalledWith("磁盘已满");
  expect(btn.disabled).toBe(false);
});

test("成绩页可选择 PNG 图片格式导出", async function () {
  await activate();
  const select = document.querySelector(".export-format-select");
  expect(select.value).toBe("pdf");
  select.value = "png";

  fire(document.querySelector(".export-btn"), "click");
  await settle();

  expect(calls.filter(function (c) { return c.method === "export_report"; })[0].payload)
    .toEqual({ session_id: "s1", format: "png" });
  expect(window.CS.toast.success).toHaveBeenCalledWith("成绩单已保存：D:/reports/s1.png");
  expect(select.disabled).toBe(false);
});

test("返回首页标记缓存失效并跳转设置页", async function () {
  await activate();
  window.CS.pages.result.goHome();

  expect(window.CS.state.historyCacheDirty).toBe(true);
  expect(window.CS.state.wrongBookCacheDirty).toBe(true);
  expect(window.CS.router.showPage).toHaveBeenCalledWith("page-settings");
});

test("订正列表按设置页每页题数分页且跨页答案保留", async function () {
  const data = practice();
  data.result.wrong_answers = Array.from({ length: 12 }, function (_, i) {
    return { seq: i, expression: i + " + 1 = ( )", answer: i + 1, user_answer: 0 };
  });
  window.CS.state.practice = data;
  responses.get_settings = function () { return { per_page: 5 }; };
  await activate();

  expect(document.getElementById("correction-pageinfo").textContent)
    .toBe("第 1 / 3 页 · 共 12 题");
  expect(inputs()).toHaveLength(5);
  const first = inputs()[0];
  first.value = "7";
  fire(first, "input");

  fire(document.getElementById("correction-next"), "click");
  expect(document.getElementById("correction-pageinfo").textContent)
    .toBe("第 2 / 3 页 · 共 12 题");
  fire(document.getElementById("correction-prev"), "click");
  expect(inputs()[0].value).toBe("7");
});

test("没有练习结果时展示空状态", async function () {
  window.CS.state.practice = null;
  await activate();

  expect(document.querySelector(".empty-hint").classList.contains("hidden")).toBe(false);
  expect(document.querySelector(".result-hero").classList.contains("hidden")).toBe(true);
  expect(document.querySelector(".wrong-card").classList.contains("hidden")).toBe(true);
});
