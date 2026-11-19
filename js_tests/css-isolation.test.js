"use strict";

/* CSS 选择器隔离回归测试（Jest）。
 *
 * 背景：错题本与结果页的订正卡曾共用 .wrong-card / .wrong-row，
 * 两份样式表同时加载时错题本的 grid 覆盖结果页的 flex，导致序号与
 * 算式错层。这里静态守卫两页的卡片/行选择器互不重叠。
 */

const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const resultCss = fs.readFileSync(path.join(root, "web/css/result.css"), "utf8");
const wrongbookCss = fs.readFileSync(path.join(root, "web/css/wrongbook.css"), "utf8");
const resultJs = fs.readFileSync(path.join(root, "web/js/pages/result.js"), "utf8");
const wrongbookJs = fs.readFileSync(path.join(root, "web/js/pages/wrongbook.js"), "utf8");

test("结果页与错题本不共用卡片/行/表头选择器", function () {
  for (const selector of ["wrong-card", "wrong-row", "wrong-columns"]) {
    const pattern = new RegExp("\\." + selector + "\\b");
    expect(pattern.test(resultCss) && pattern.test(wrongbookCss)).toBe(false);
  }
});

test("两页脚本使用各自命名空间生成行元素", function () {
  expect(resultJs).toMatch(/row\.className = "wrong-row"/);
  expect(resultJs).not.toMatch(/"wb-row"/);
  expect(wrongbookJs).toMatch(/class="wb-row"/);
  expect(wrongbookJs).not.toMatch(/class="wrong-row"/);
});
