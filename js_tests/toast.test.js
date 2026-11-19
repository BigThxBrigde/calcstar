"use strict";

const { reset, load, fire } = require("./support");

beforeEach(function () {
  jest.useFakeTimers();
  reset();
  load("toast.js");
});

afterEach(function () {
  jest.useRealTimers();
});

function items() {
  return document.querySelectorAll(".toast-container > .toast");
}

test("三种提示均创建带图标与文案的 toast", function () {
  window.CS.toast.success("成功啦");
  window.CS.toast.error("失败了");
  window.CS.toast.info("提示一下");

  const container = document.querySelector(".toast-container");
  expect(container.getAttribute("aria-live")).toBe("polite");
  expect(items()).toHaveLength(3);
  expect(items()[0].className).toContain("toast-success");
  expect(items()[0].querySelector(".toast-text").textContent).toBe("成功啦");
  expect(items()[0].querySelector(".toast-icon svg")).not.toBeNull();
  expect(items()[1].className).toContain("toast-error");
  expect(items()[2].className).toContain("toast-info");
});

test("默认 2600ms 后进入退场态，animationend 时移除", function () {
  const item = window.CS.toast.success("保存成功");

  jest.advanceTimersByTime(2599);
  expect(item.classList.contains("toast-out")).toBe(false);

  jest.advanceTimersByTime(1);
  expect(item.classList.contains("toast-out")).toBe(true);

  fire(item, "animationend");
  expect(document.body.contains(item)).toBe(false);
});

test("点击 toast 立即进入退场态且不会重复触发", function () {
  const item = window.CS.toast.info("点我关闭");

  fire(item, "click");
  fire(item, "click");

  expect(item.classList.contains("toast-out")).toBe(true);
  expect(item.addEventListener).toBeDefined();
  jest.advanceTimersByTime(5000);
  expect(document.body.contains(item)).toBe(false);
});

test("自定义时长生效，动画未触发时 400ms 兜底移除", function () {
  const item = window.CS.toast.error("出错了", 100);

  jest.advanceTimersByTime(100);
  expect(item.classList.contains("toast-out")).toBe(true);

  jest.advanceTimersByTime(399);
  expect(document.body.contains(item)).toBe(true);
  jest.advanceTimersByTime(1);
  expect(document.body.contains(item)).toBe(false);
});
