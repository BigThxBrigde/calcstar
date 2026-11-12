"use strict";

/* CalcStar 设置页：参数选择、前端校验与创建练习 */
window.CS = window.CS || {};
CS.pages = CS.pages || {};

CS.pages.settings = (function () {
  // 校验约束与后端 src/calcstar/config.py 的 validate_params 保持一致
  const LIMITS = {
    range: { min: 1, max: 999, label: "数值范围" },
    count: { min: 1, max: 200, label: "题目数量" },
    duration: { min: 1, max: 180, label: "限时分钟数" }
  };

  const els = {};
  let starting = false;

  function $(id) {
    return document.getElementById(id);
  }

  function getChecked(name) {
    const input = document.querySelector('input[name="' + name + '"]:checked');
    return input ? input.value : null;
  }

  /** 严格解析非负整数，非法返回 NaN */
  function parseIntStrict(text) {
    return /^\d+$/.test(text) ? Number(text) : NaN;
  }

  /** 解析「预设单选 + 自定义输入」组合，返回 {ok, value} 或 {ok:false, message} */
  function collectPresetOrCustom(name, limits) {
    const choice = getChecked(name);
    if (!choice) {
      return { ok: false, message: "请先选择" + limits.label };
    }
    if (choice !== "custom") {
      return { ok: true, value: parseIntStrict(choice) };
    }
    const input = $(name === "range" ? "custom-range"
      : name === "count" ? "custom-count" : "custom-duration");
    const value = parseIntStrict((input.value || "").trim());
    if (!Number.isInteger(value) || value < limits.min || value > limits.max) {
      return {
        ok: false,
        message: limits.label + "需为 " + limits.min + "~" + limits.max + " 之间的整数"
      };
    }
    return { ok: true, value: value };
  }

  /** 收集并校验全部设置，返回 {ok:true, config} 或 {ok:false, message} */
  function collectConfig() {
    const category = getChecked("category");
    if (!category) {
      return { ok: false, message: "请先选择运算类别" };
    }

    const rangeRes = collectPresetOrCustom("range", LIMITS.range);
    if (!rangeRes.ok) {
      return rangeRes;
    }

    const countRes = collectPresetOrCustom("count", LIMITS.count);
    if (!countRes.ok) {
      return countRes;
    }

    // 限时：不限时为 null；其余为分钟数
    const durationChoice = getChecked("duration");
    let durationMinutes = null;
    if (durationChoice === "custom") {
      const durRes = collectPresetOrCustom("duration", LIMITS.duration);
      if (!durRes.ok) {
        return durRes;
      }
      durationMinutes = durRes.value;
    } else if (durationChoice && durationChoice !== "none") {
      durationMinutes = parseIntStrict(durationChoice);
    }

    const perPageRaw = getChecked("per-page");
    const perPage = perPageRaw ? parseIntStrict(perPageRaw) : NaN;
    if (!Number.isInteger(perPage)) {
      return { ok: false, message: "请选择每页题数" };
    }

    const config = {
      category: category,
      range_n: rangeRes.value,
      count: countRes.value,
      duration_minutes: durationMinutes,
      allow_negative: els.allowNegative.checked,
      include_parentheses: category === "mixed" && els.parentheses.checked,
      per_page: perPage
    };
    return { ok: true, config: config };
  }

  /** 「自定义」单选展开输入框，选中预设时收起 */
  function wireCustomGroup(name, rowId, inputId) {
    const radios = document.querySelectorAll('input[name="' + name + '"]');
    const row = $(rowId);
    const input = $(inputId);
    radios.forEach(function (radio) {
      radio.addEventListener("change", function () {
        if (!radio.checked) {
          return;
        }
        const isCustom = radio.value === "custom";
        row.classList.toggle("hidden", !isCustom);
        if (isCustom) {
          input.focus();
        }
      });
    });
  }

  /** 括号开关仅四则混合（mixed）可用，切走时自动复位为关闭 */
  function updateParenthesesState() {
    const isMixed = getChecked("category") === "mixed";
    els.parentheses.disabled = !isMixed;
    if (!isMixed) {
      els.parentheses.checked = false;
    }
    els.rowParentheses.classList.toggle("is-disabled", !isMixed);
  }

  /** 开始练习：校验 → create_practice → 存 state → 跳练习页 */
  async function startPractice() {
    if (starting) {
      return;
    }

    const collected = collectConfig();
    if (!collected.ok) {
      CS.toast.error(collected.message);
      return;
    }

    starting = true;
    els.startBtn.disabled = true;
    const label = els.startBtn.querySelector(".btn-label");
    const originalLabel = label.textContent;
    label.textContent = "正在生成…";

    try {
      const data = await CS.api.callBridge("create_practice", collected.config);
      CS.state.currentSession = data;
      CS.state.config = collected.config;
      CS.state.answers = {};
      CS.state.startedAt = Date.now();
      CS.router.showPage("page-practice");
      CS.toast.success("练习已生成，加油哦！");
    } catch (err) {
      CS.toast.error(err && err.message ? err.message : "生成练习失败，请重试");
    } finally {
      starting = false;
      els.startBtn.disabled = false;
      label.textContent = originalLabel;
    }
  }

  function init() {
    els.allowNegative = $("allow-negative");
    els.parentheses = $("with-parentheses");
    els.rowParentheses = $("row-parentheses");
    els.startBtn = $("start-btn");

    document.querySelectorAll('input[name="category"]').forEach(function (radio) {
      radio.addEventListener("change", updateParenthesesState);
    });
    updateParenthesesState();

    wireCustomGroup("range", "row-custom-range", "custom-range");
    wireCustomGroup("count", "row-custom-count", "custom-count");
    wireCustomGroup("duration", "row-custom-duration", "custom-duration");

    els.startBtn.addEventListener("click", startPractice);

    // 提前连接桥接，缺席时给出明确提示（普通浏览器打开页面时）
    CS.api.ready().catch(function (err) {
      CS.toast.error(err && err.message ? err.message : "无法连接后端");
    });
  }

  init();

  return {
    init: init,
    collectConfig: collectConfig,
    startPractice: startPractice
  };
})();
