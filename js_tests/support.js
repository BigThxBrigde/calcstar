"use strict";

const path = require("path");

const webRoot = path.resolve(__dirname, "..", "web", "js");

function scriptPath(relative) {
  return path.join(webRoot, relative);
}

/** 清除 DOM 与共享命名空间，并让下一次 require 重新执行前端脚本 */
function reset() {
  jest.resetModules();
  document.body.innerHTML = "";
  window.CS = {};
}

/** 加载 web/js 下的脚本（相对路径，如 "api.js" / "pages/history.js"） */
function load(relative) {
  require(scriptPath(relative));
}

/** 桥接桩：记录调用并按 method 分派返回值 */
function stubApi(responses) {
  const calls = [];
  window.CS.api = {
    ready: jest.fn(function () { return Promise.resolve(); }),
    callBridge: jest.fn(function (method, payload) {
      calls.push({ method: method, payload: payload });
      const handler = responses && responses[method];
      if (!handler) {
        return Promise.reject(new Error("未预期的桥接方法 " + method));
      }
      return Promise.resolve().then(function () { return handler(payload); });
    })
  };
  return calls;
}

function stubShell() {
  window.CS.router = {
    PAGE_IDS: [
      "page-settings", "page-practice", "page-result",
      "page-history", "page-wrongbook"
    ],
    showPage: jest.fn(),
    currentPageId: jest.fn(function () { return null; })
  };
  window.CS.toast = {
    success: jest.fn(),
    error: jest.fn(),
    info: jest.fn()
  };
  window.CS.mask = { show: jest.fn(), hide: jest.fn() };
}

async function flush(times) {
  const count = times || 5;
  for (let i = 0; i < count; i++) {
    await Promise.resolve();
  }
  await new Promise(function (resolve) { setTimeout(resolve, 0); });
}

function fire(el, type, props) {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.assign(event, props || {});
  el.dispatchEvent(event);
  return event;
}

module.exports = {
  webRoot: webRoot,
  scriptPath: scriptPath,
  reset: reset,
  load: load,
  stubApi: stubApi,
  stubShell: stubShell,
  flush: flush,
  fire: fire
};
