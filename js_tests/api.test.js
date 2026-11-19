"use strict";

const { reset, load } = require("./support");

afterEach(function () {
  delete global.qt;
  delete global.QWebChannel;
});

function installBridge(bridge) {
  global.qt = { webChannelTransport: { transport: "stub" } };
  global.QWebChannel = jest.fn(function (transport, callback) {
    callback({ objects: { bridge: bridge } });
  });
}

test("缺少 Qt 环境时 ready 给出明确错误", async function () {
  reset();
  load("api.js");

  await expect(window.CS.api.ready()).rejects.toThrow("未检测到 Qt 桌面环境");
});

test("QWebChannel 未加载时 ready 给出明确错误", async function () {
  reset();
  global.qt = { webChannelTransport: {} };
  load("api.js");

  await expect(window.CS.api.ready()).rejects.toThrow("QWebChannel 未加载");
});

test("bridge 未注册时 ready 拒绝且不缓存失败结果", async function () {
  reset();
  global.qt = { webChannelTransport: {} };
  global.QWebChannel = function (transport, callback) { callback({ objects: {} }); };
  load("api.js");

  await expect(window.CS.api.ready()).rejects.toThrow("bridge 未注册");
  await expect(window.CS.api.ready()).rejects.toThrow("bridge 未注册");
});

test("ready 缓存同一个 bridge，只建立一次连接", async function () {
  reset();
  const bridge = {};
  installBridge(bridge);
  load("api.js");

  await expect(window.CS.api.ready()).resolves.toBe(bridge);
  await expect(window.CS.api.ready()).resolves.toBe(bridge);
  expect(global.QWebChannel).toHaveBeenCalledTimes(1);
  expect(global.QWebChannel.mock.calls[0][0]).toBe(global.qt.webChannelTransport);
});

test("callBridge 序列化 payload，解包 ok 响应", async function () {
  reset();
  const bridge = {
    create_practice: jest.fn(function (raw) {
      expect(raw).toBe('{"count":5}');
      return JSON.stringify({ ok: true, data: { session_id: "s1" } });
    })
  };
  installBridge(bridge);
  load("api.js");

  await expect(window.CS.api.callBridge("create_practice", { count: 5 }))
    .resolves.toEqual({ session_id: "s1" });
  expect(bridge.create_practice).toHaveBeenCalledTimes(1);
});

test("callBridge 缺省 payload 序列化为空对象", async function () {
  reset();
  const bridge = {
    get_settings: jest.fn(function () {
      return JSON.stringify({ ok: true, data: {} });
    })
  };
  installBridge(bridge);
  load("api.js");

  await window.CS.api.callBridge("get_settings");
  expect(bridge.get_settings).toHaveBeenCalledWith("{}");
});

test("callBridge 覆盖后端不存在、抛错、坏 JSON 与 ok=false 四类失败", async function () {
  reset();
  installBridge({
    explode: function () { throw new Error("后端崩了"); },
    garbage: function () { return "not json"; },
    rejected: function () { return JSON.stringify({ ok: false, error: "参数非法" }); },
    unknown: function () { return "{}"; }
  });
  load("api.js");

  await expect(window.CS.api.callBridge("missing")).rejects.toThrow("后端方法不存在：missing");
  await expect(window.CS.api.callBridge("explode")).rejects.toThrow("调用后端失败：后端崩了");
  await expect(window.CS.api.callBridge("garbage")).rejects.toThrow("后端返回数据解析失败");
  await expect(window.CS.api.callBridge("rejected")).rejects.toThrow("参数非法");
  await expect(window.CS.api.callBridge("unknown")).rejects.toThrow("后端返回未知错误");
});
