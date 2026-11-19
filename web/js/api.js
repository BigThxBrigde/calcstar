"use strict";

/* CalcStar 桥接 API：等待 QWebChannel 就绪并统一封装后端调用 */
window.CS = window.CS || {};

CS.api = (function () {
  let bridgePromise = null;

  /** 等待桥接对象就绪（结果缓存，可重复调用） */
  function ensureBridge() {
    if (bridgePromise) {
      return bridgePromise;
    }
    bridgePromise = new Promise(function (resolve, reject) {
      if (typeof qt === "undefined" || !qt || !qt.webChannelTransport) {
        reject(new Error("未检测到 Qt 桌面环境，无法连接后端"));
        return;
      }
      if (typeof QWebChannel !== "function") {
        reject(new Error("QWebChannel 未加载"));
        return;
      }
      new QWebChannel(qt.webChannelTransport, function (channel) {
        if (channel.objects && channel.objects.bridge) {
          resolve(channel.objects.bridge);
        } else {
          reject(new Error("后端桥接对象 bridge 未注册"));
        }
      });
    });
    // 瞬时失败（如桥接尚未注册）不缓存，允许后续调用重试。
    bridgePromise.catch(function () {
      bridgePromise = null;
    });
    return bridgePromise;
  }

  /**
   * 调用后端桥接方法。
   * @param {string} method 桥接方法名，如 "create_practice"
   * @param {Object} payload 参数对象（序列化为 JSON 字符串传递）
   * @returns {Promise<Object>} ok=true 时 resolve data；否则 reject Error(error)
   */
  async function callBridge(method, payload) {
    let bridge;
    try {
      bridge = await ensureBridge();
    } catch (err) {
      throw new Error(err?.message || String(err));
    }

    if (typeof bridge[method] !== "function") {
      throw new Error("后端方法不存在：" + method);
    }

    let raw;
    try {
      raw = await bridge[method](JSON.stringify(payload || {}));
    } catch (err) {
      throw new Error("调用后端失败：" + (err?.message || err));
    }

    let envelope;
    try {
      envelope = JSON.parse(raw);
    } catch (err) {
      throw new Error("后端返回数据解析失败");
    }

    if (envelope && envelope.ok) {
      return envelope.data;
    }
    throw new Error((envelope && envelope.error) || "后端返回未知错误");
  }

  return {
    ready: ensureBridge,
    callBridge: callBridge
  };
})();
