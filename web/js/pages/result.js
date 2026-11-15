"use strict";

/* CalcStar 结果与订正页（Task 7）
 *
 * 读取的共享状态字段（window.CS.state）：
 *   - practice：练习页（practice.js）提交成功后写入
 *     {sessionId, result:{score, correct_count, total_count, passed,
 *      wrong_answers:[{seq, expression, answer, user_answer}]},
 *      elapsedSeconds, timedOut}。
 *   - currentSession：session_id 兜底（订正提交需要会话 id）。
 *
 * 写入的共享状态字段：
 *   - practice.result.wrong_answers：订正循环中按后端返回更新剩余错题；
 *     全部订正通过时置 result.passed = true、wrong_answers = []。
 *   - practice.correctionRound：已完成订正轮数（来自 submit_correction
 *     返回的 correction_round）。
 *   - historyCacheDirty / wrongBookCacheDirty：返回首页前置为 true，
 *     供历史页 / 错题本页（Task 8）感知数据变更并重新拉取；
 *     同时删除可能存在的 historyCache / wrongBookCache 缓存字段。
 */

window.CS = window.CS || {};
CS.pages = CS.pages || {};

CS.pages.result = (function () {
  const ICON_TROPHY =
    '<svg viewBox="0 0 24 24" width="44" height="44" fill="currentColor" aria-hidden="true"><path d="M19 5h-2V3H7v2H5c-1.1 0-2 .9-2 2v1c0 2.55 1.92 4.63 4.39 4.94.63 1.5 1.98 2.63 3.61 2.96V19H7v2h10v-2h-4v-3.1c1.63-.33 2.98-1.46 3.61-2.96C19.08 12.63 21 10.55 21 8V7c0-1.1-.9-2-2-2zM5 8V7h2v3.82C5.84 10.4 5 9.3 5 8zm14 0c0 1.3-.84 2.4-2 2.82V7h2v1z"/></svg>';
  const ICON_STAR =
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>';
  const ICON_PENCIL =
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
  const ICON_HOME =
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>';
  const ICON_DOWNLOAD =
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M5 20h14v-2H5v2zM19 9h-4V3H9v6H5l7 7 7-7z"/></svg>';
  const STAR_DECO =
    '<svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>';

  const MAX_INPUT_LEN = 8;

  const pageEl = document.getElementById("page-result");

  let data = null;                 // CS.state.practice
  let submittingCorrection = false;
  let exportingReport = false;
  let correctionInputs = {};       // seq字符串 → input 元素
  let built = false;

  const els = {};

  /* ---------- 工具 ---------- */

  /** 解析订正输入：合法整数返回 Number，空/半截返回 null */
  function parseAnswer(raw) {
    const v = String(raw == null ? "" : raw).trim();
    if (!/^-?\d+$/.test(v)) {
      return null;
    }
    return Number(v);
  }

  /** 清洗输入：仅保留数字与开头一个负号，去前导零 */
  function sanitizeInput(raw) {
    const negative = raw.charAt(0) === "-";
    const digits = raw.replace(/[^0-9]/g, "").replace(/^0+(?=\d)/, "");
    return (negative ? "-" : "") + digits;
  }

  function fmtDuration(totalSeconds) {
    const s = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) {
      return h + "小时" + m + "分" + sec + "秒";
    }
    if (m > 0) {
      return m + "分" + (sec < 10 ? "0" + sec : sec) + "秒";
    }
    return sec + "秒";
  }

  /** 标记历史/错题本缓存失效（Task 8 页面据此重新拉取） */
  function markCachesDirty() {
    CS.state.historyCacheDirty = true;
    CS.state.wrongBookCacheDirty = true;
    delete CS.state.historyCache;
    delete CS.state.wrongBookCache;
  }

  /* ---------- 骨架 ---------- */

  function buildSkeleton() {
    if (built || !pageEl) {
      return;
    }
    pageEl.innerHTML =
      '<div class="result-hero card">' +
      '  <span class="celebrate-star s1" aria-hidden="true">' + STAR_DECO + "</span>" +
      '  <span class="celebrate-star s2" aria-hidden="true">' + STAR_DECO + "</span>" +
      '  <span class="celebrate-star s3" aria-hidden="true">' + STAR_DECO + "</span>" +
      '  <span class="celebrate-star s4" aria-hidden="true">' + STAR_DECO + "</span>" +
      '  <span class="celebrate-star s5" aria-hidden="true">' + STAR_DECO + "</span>" +
      '  <div class="result-trophy">' + ICON_TROPHY + "</div>" +
      '  <div class="score-ring">' +
      '    <div class="score-core">' +
      '      <span class="score-num">0</span>' +
      '      <span class="score-unit">得分</span>' +
      "    </div>" +
      "  </div>" +
      '  <h2 class="result-title"></h2>' +
      '  <p class="result-sub"></p>' +
      '  <div class="result-stats">' +
      '    <span class="stat-chip"><span class="chip-label">正确率</span><span class="chip-value"></span></span>' +
      '    <span class="stat-chip"><span class="chip-label">答对</span><span class="chip-value"></span></span>' +
      '    <span class="stat-chip"><span class="chip-label">用时</span><span class="chip-value"></span></span>' +
      '    <span class="stat-chip is-timeout hidden">超时自动提交</span>' +
      "  </div>" +
      '  <div class="result-actions">' +
      '    <button type="button" class="btn-primary home-btn"><span class="btn-label">返回首页</span>' + ICON_HOME + "</button>" +
      '    <button type="button" class="btn-soft export-btn"><span class="btn-label">导出成绩单</span>' + ICON_DOWNLOAD + "</button>" +
      "  </div>" +
      "</div>" +
      '<div class="wrong-card card">' +
      '  <h2 class="card-title">' +
      '    <span class="ticon wrong-ticon">' + ICON_PENCIL + "</span>错题订正" +
      '    <span class="round-badge hidden"></span>' +
      "  </h2>" +
      '  <div class="wrong-list"></div>' +
      '  <div class="wrong-footer">' +
      '    <button type="button" class="btn-primary correction-btn"><span class="btn-label">提交订正</span>' + ICON_STAR + "</button>" +
      '    <button type="button" class="btn-soft quit-btn">先不订正，回首页</button>' +
      "  </div>" +
      "</div>" +
      '<p class="passed-note hidden">错题全部订正通过，太厉害啦！</p>' +
      '<div class="empty-hint hidden">' +
      "  <p>还没有成绩哦，先回首页开始一局吧！</p>" +
      '  <button type="button" class="btn-soft empty-home-btn">回首页</button>' +
      "</div>";

    els.hero = pageEl.querySelector(".result-hero");
    els.scoreNum = pageEl.querySelector(".score-num");
    els.title = pageEl.querySelector(".result-title");
    els.sub = pageEl.querySelector(".result-sub");
    els.statValues = pageEl.querySelectorAll(".result-stats .stat-chip:not(.is-timeout) .chip-value");
    els.timeoutChip = pageEl.querySelector(".stat-chip.is-timeout");
    els.homeBtn = pageEl.querySelector(".home-btn");
    els.exportBtn = pageEl.querySelector(".export-btn");
    els.exportLabel = pageEl.querySelector(".export-btn .btn-label");
    els.wrongCard = pageEl.querySelector(".wrong-card");
    els.roundBadge = pageEl.querySelector(".round-badge");
    els.wrongList = pageEl.querySelector(".wrong-list");
    els.correctionBtn = pageEl.querySelector(".correction-btn");
    els.correctionLabel = pageEl.querySelector(".correction-btn .btn-label");
    els.quitBtn = pageEl.querySelector(".quit-btn");
    els.passedNote = pageEl.querySelector(".passed-note");
    els.emptyHint = pageEl.querySelector(".empty-hint");
    els.emptyHomeBtn = pageEl.querySelector(".empty-home-btn");

    els.homeBtn.addEventListener("click", goHome);
    els.quitBtn.addEventListener("click", goHome);
    els.emptyHomeBtn.addEventListener("click", goHome);
    els.exportBtn.addEventListener("click", function () {
      exportReport();
    });
    els.correctionBtn.addEventListener("click", function () {
      submitCorrection();
    });

    built = true;
  }

  /* ---------- 渲染 ---------- */

  function render() {
    const d = CS.state.practice;
    if (!d || !d.result || typeof d.result !== "object") {
      showEmpty();
      return;
    }
    data = d;
    markCachesDirty();

    const r = data.result;
    const total = Number(r.total_count) || 0;
    const correct = Number(r.correct_count) || 0;
    const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;

    els.scoreNum.textContent = String(r.score);
    els.statValues[0].textContent = accuracy + "%";
    els.statValues[1].textContent = correct + " / " + total + " 题";
    els.statValues[2].textContent = fmtDuration(Number(data.elapsedSeconds) || 0);
    els.timeoutChip.classList.toggle("hidden", !data.timedOut);

    const allDone = r.passed === true;
    els.hero.classList.toggle("is-celebrate", allDone);
    if (allDone) {
      els.title.textContent = data.correctionRound > 0
        ? "错题全部订正通过！"
        : "太棒啦，全部答对！";
      els.sub.textContent = "你就是口算小达人！";
    } else {
      els.title.textContent = "答完啦，来把错题订正一下吧！";
      els.sub.textContent = "别灰心，订正全对也一样棒！";
    }
    els.homeBtn.classList.toggle("hidden", !allDone);
    els.exportBtn.classList.remove("hidden");
    els.wrongCard.classList.toggle("hidden", allDone);
    els.passedNote.classList.toggle("hidden", !allDone);

    if (!allDone) {
      renderWrongList(r.wrong_answers || []);
    }
  }

  function renderWrongList(wrongAnswers) {
    els.wrongList.innerHTML = "";
    correctionInputs = {};

    const list = Array.isArray(wrongAnswers) ? wrongAnswers : [];
    const frag = document.createDocumentFragment();
    list.forEach(function (item) {
      frag.appendChild(buildWrongRow(item));
    });
    els.wrongList.appendChild(frag);

    const round = Number(data.correctionRound) || 0;
    els.roundBadge.textContent = "已完成 " + round + " 轮订正";
    els.roundBadge.classList.toggle("hidden", round <= 0);
  }

  function buildWrongRow(item) {
    const row = document.createElement("div");
    row.className = "wrong-row";

    const seq = document.createElement("span");
    seq.className = "wrong-seq";
    seq.textContent = String(item.seq + 1);
    seq.setAttribute("aria-hidden", "true");

    const expr = document.createElement("span");
    expr.className = "wrong-expression";
    expr.textContent = item.expression;

    const userPill = document.createElement("span");
    userPill.className = "ans-pill ans-user";
    userPill.innerHTML = '<span class="ans-label">你的答案</span>';
    const userValue = document.createElement("span");
    userValue.textContent =
      item.user_answer == null ? "未作答" : String(item.user_answer);
    userPill.appendChild(userValue);

    const correctPill = document.createElement("span");
    correctPill.className = "ans-pill ans-correct";
    correctPill.innerHTML = '<span class="ans-label">正确答案</span>';
    const correctValue = document.createElement("span");
    correctValue.textContent = String(item.answer);
    correctPill.appendChild(correctValue);

    const input = document.createElement("input");
    input.type = "text";
    input.className = "correction-input";
    input.inputMode = "numeric";
    input.autocomplete = "off";
    input.maxLength = MAX_INPUT_LEN;
    input.placeholder = "再算一遍";
    input.setAttribute("aria-label", "第" + (item.seq + 1) + "题订正答案");
    input.dataset.seq = String(item.seq);
    correctionInputs[String(item.seq)] = input;

    const seqKey = String(item.seq);
    const rowEl = row;
    input.addEventListener("input", function () {
      const clean = sanitizeInput(input.value);
      if (clean !== input.value) {
        input.value = clean;
      }
      rowEl.classList.toggle("is-filled", parseAnswer(clean) !== null);
    });
    input.addEventListener("focus", function () {
      input.select();
    });
    input.addEventListener("keydown", function (ev) {
      if (ev.key !== "Enter") {
        return;
      }
      ev.preventDefault();
      const inputs = Object.keys(correctionInputs)
        .sort(function (a, b) { return Number(a) - Number(b); })
        .map(function (k) { return correctionInputs[k]; });
      const idx = inputs.indexOf(input);
      if (idx > -1 && idx < inputs.length - 1) {
        inputs[idx + 1].focus();
      } else {
        els.correctionBtn.focus();
      }
    });

    row.appendChild(seq);
    row.appendChild(expr);
    row.appendChild(userPill);
    row.appendChild(correctPill);
    row.appendChild(input);
    return row;
  }

  function showEmpty() {
    data = null;
    els.hero.classList.add("hidden");
    els.exportBtn.classList.add("hidden");
    els.wrongCard.classList.add("hidden");
    els.passedNote.classList.add("hidden");
    els.emptyHint.classList.remove("hidden");
  }

  /* ---------- 订正循环 ---------- */

  async function submitCorrection() {
    if (submittingCorrection || !data || !data.result) {
      return;
    }
    const list = data.result.wrong_answers || [];
    if (list.length === 0) {
      return;
    }

    const corrections = {};
    let missing = 0;
    list.forEach(function (item) {
      const input = correctionInputs[String(item.seq)];
      const value = parseAnswer(input ? input.value : "");
      if (value === null) {
        missing += 1;
      } else {
        corrections[String(item.seq)] = value;
      }
    });
    if (missing > 0) {
      CS.toast.info("还有 " + missing + " 题没填订正答案哦！");
      return;
    }

    const sessionId = data.sessionId ||
      (CS.state.currentSession && CS.state.currentSession.session_id);
    if (sessionId == null) {
      CS.toast.error("找不到练习会话，无法提交订正");
      return;
    }

    submittingCorrection = true;
    els.correctionBtn.disabled = true;
    els.correctionLabel.textContent = "判分中…";

    try {
      const res = await CS.api.callBridge("submit_correction", {
        session_id: sessionId,
        corrections: corrections
      });
      markCachesDirty();
      data.correctionRound = Number(res.correction_round) || 0;

      if (res.all_correct || res.passed) {
        data.result.wrong_answers = [];
        data.result.passed = true;
        CS.toast.success("订正全部通过，你真棒！");
        render();
      } else {
        data.result.wrong_answers = Array.isArray(res.wrong_answers)
          ? res.wrong_answers
          : [];
        render();
        CS.toast.info("还剩 " + data.result.wrong_answers.length + " 题要再想想哦！");
        focusFirstCorrectionInput();
      }
    } catch (err) {
      CS.toast.error(err && err.message ? err.message : "提交订正失败，请重试");
    } finally {
      submittingCorrection = false;
      els.correctionBtn.disabled = false;
      els.correctionLabel.textContent = "提交订正";
    }
  }

  function focusFirstCorrectionInput() {
    const seqs = Object.keys(correctionInputs)
      .map(Number)
      .sort(function (a, b) { return a - b; });
    if (seqs.length > 0) {
      const first = correctionInputs[String(seqs[0])];
      if (first) {
        first.focus();
      }
    }
  }

  /* ---------- 导出成绩单 ---------- */

  /** 调用后端导出本次练习成绩单 PDF（含逐题明细） */
  async function exportReport() {
    if (exportingReport || !data) {
      return;
    }
    const sessionId = data.sessionId ||
      (CS.state.currentSession && CS.state.currentSession.session_id);
    if (sessionId == null) {
      CS.toast.error("找不到练习会话，无法导出");
      return;
    }

    exportingReport = true;
    els.exportBtn.disabled = true;
    els.exportLabel.textContent = "导出中…";
    CS.mask.show("正在生成成绩单…");

    try {
      const res = await CS.api.callBridge("export_report_pdf", {
        session_id: sessionId
      });
      if (res && res.cancelled) {
        CS.toast.info("已取消导出");
      } else if (res && res.path) {
        CS.toast.success("成绩单已保存：" + res.path);
      } else {
        CS.toast.error("导出失败，请重试");
      }
    } catch (err) {
      CS.toast.error(err && err.message ? err.message : "导出失败，请重试");
    } finally {
      exportingReport = false;
      els.exportBtn.disabled = false;
      els.exportLabel.textContent = "导出成绩单";
      CS.mask.hide();
    }
  }

  /* ---------- 返回首页 ---------- */

  function goHome() {
    markCachesDirty();
    CS.router.showPage("page-settings");
  }

  /* ---------- 激活（配合 router 切页） ---------- */

  function activate() {
    if (!pageEl || !pageEl.classList.contains("active")) {
      return;
    }
    buildSkeleton();
    els.hero.classList.remove("hidden");
    els.wrongCard.classList.remove("hidden");
    els.emptyHint.classList.add("hidden");
    render();
  }

  function init() {
    if (!pageEl) {
      return;
    }
    buildSkeleton();
    const observer = new MutationObserver(function () {
      if (pageEl.classList.contains("active")) {
        activate();
      }
    });
    observer.observe(pageEl, { attributes: true, attributeFilter: ["class"] });
  }

  init();

  return {
    activate: activate,
    submitCorrection: submitCorrection,
    goHome: goHome
  };
})();
