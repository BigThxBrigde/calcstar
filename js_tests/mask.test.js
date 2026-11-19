"use strict";

const { reset, load } = require("./support");

test("show 创建唯一遮罩并更新文案与无障碍属性", function () {
  reset();
  load("mask.js");

  window.CS.mask.show("正在生成…");
  window.CS.mask.show("正在保存…");

  const masks = document.querySelectorAll(".cs-mask");
  expect(masks).toHaveLength(1);
  const mask = masks[0];
  expect(mask.getAttribute("role")).toBe("status");
  expect(mask.getAttribute("aria-live")).toBe("polite");
  expect(mask.querySelector(".cs-mask-spinner").getAttribute("aria-hidden")).toBe("true");
  expect(mask.querySelector(".cs-mask-text").textContent).toBe("正在保存…");
  expect(mask.classList.contains("is-visible")).toBe(true);
});

test("show 无文案时使用默认值", function () {
  reset();
  load("mask.js");

  window.CS.mask.show("");

  expect(document.querySelector(".cs-mask-text").textContent).toBe("处理中…");
});

test("hide 仅隐藏而不销毁，未显示时调用不报错", function () {
  reset();
  load("mask.js");

  expect(function () { window.CS.mask.hide(); }).not.toThrow();

  window.CS.mask.show("加载中");
  window.CS.mask.hide();

  const mask = document.querySelector(".cs-mask");
  expect(mask).not.toBeNull();
  expect(mask.classList.contains("is-visible")).toBe(false);
});

test("遮罩被外部移除后再次 show 会重建", function () {
  reset();
  load("mask.js");

  window.CS.mask.show("第一次");
  document.querySelector(".cs-mask").remove();
  window.CS.mask.show("第二次");

  const masks = document.querySelectorAll(".cs-mask");
  expect(masks).toHaveLength(1);
  expect(masks[0].querySelector(".cs-mask-text").textContent).toBe("第二次");
});
