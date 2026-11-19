"use strict";

const { reset, load } = require("./support");

function makePages() {
  window.CS.router.PAGE_IDS.forEach(function (id) {
    const el = document.createElement("div");
    el.id = id;
    document.body.appendChild(el);
  });
}

beforeEach(function () {
  jest.spyOn(console, "error").mockImplementation(function () {});
});

afterEach(function () {
  console.error.mockRestore();
});

test("showPage 只激活目标页并记录当前页", function () {
  reset();
  load("router.js");
  makePages();

  expect(window.CS.router.showPage("page-practice")).toBe(true);
  expect(document.getElementById("page-practice").classList.contains("active")).toBe(true);
  expect(window.CS.router.PAGE_IDS.every(function (id) {
    return id === "page-practice" || !document.getElementById(id).classList.contains("active");
  })).toBe(true);
  expect(window.CS.router.currentPageId()).toBe("page-practice");

  window.CS.router.showPage("page-history");
  expect(document.getElementById("page-practice").classList.contains("active")).toBe(false);
  expect(document.getElementById("page-history").classList.contains("active")).toBe(true);
  expect(window.CS.router.currentPageId()).toBe("page-history");
});

test("未知 id、不存在的元素均切换失败并报错", function () {
  reset();
  load("router.js");
  makePages();

  expect(window.CS.router.showPage("page-unknown")).toBe(false);
  expect(console.error).toHaveBeenCalledWith("页面不存在：page-unknown");

  const alien = document.createElement("div");
  alien.id = "alien";
  document.body.appendChild(alien);
  expect(window.CS.router.showPage("alien")).toBe(false);
  expect(window.CS.router.currentPageId()).toBeNull();
});

test("允许部分页面元素缺席，其余页面照常切换", function () {
  reset();
  load("router.js");
  makePages();
  document.getElementById("page-result").remove();

  expect(window.CS.router.showPage("page-settings")).toBe(true);
  expect(document.getElementById("page-settings").classList.contains("active")).toBe(true);
});
