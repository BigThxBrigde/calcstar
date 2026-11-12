"use strict";

/* CalcStar 练习做题页（Task 6）
 *
 * 读取的共享状态字段（window.CS.state，由 settings.js 写入）：
 *   - currentSession：create_practice 返回数据
 *     {session_id, questions:[{seq, expression}], total_count, per_page,
 *      total_pages, duration_seconds(秒或null), category, range_n, source?}
 *     注意 seq 从 0 开始，展示时 +1。
 *   - config：设置页配置 {category, range_n, count, duration_minutes,
 *     allow_negative, include_parentheses, per_page}（per_page 兜底）。
 *   - startedAt：练习开始时间戳（毫秒），计时基准。
 *   - answers：作答表 {seq字符串: 答案字符串}（settings 页每次开新练习重置为 {}）。
 *
 * 写入的共享状态字段：
 *   - answers：输入时实时写入（seq 字符串 → 用户输入字符串）。
 *   - practice：提交成功后写入，供结果页（result.js）读取：
 *     {sessionId, result:{score, correct_count, total_count, passed,
 *      wrong_answers}, elapsedSeconds, timedOut}
 */

window.CS = window.CS || {};
CS.pages = CS.pages || {};

CS.pages.practice = (function () {
  const TICK_MS = 250;            // 计时器刷新间隔
  const AUTO_ADVANCE_MS = 650;    // 输入停顿后自动跳下一题的等待时长
  const URGENT_SECONDS = 60;      // 倒计时告急阈值（秒）
  const MAX_INPUT_LEN = 8;        // 答案最长字符数（覆盖 999×999+负号）

  const ICON_CLOCK =
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M12 2c1.1 0 2 .9 2 2s-.9 2-2 2-2-.9-2-2 .9-2 2-2zm9 7h-6.13l-2.05 3.83.81 1.17H21v2h-8.06l-1.53 2.85c.83.32 1.59.79 1.59 1.65 0 0-1 .5-4 .5s-4-.5-4-.5c0-1.43 1.49-2.19 2.79-2.87L9 15.42S11.9 10 12 10h6c1.1 0 2 .9 2 2h.01L21 9z"/></svg>';
  const ICON_STAR =
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>';
  const ICON_ARROW_LEFT =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>';
  const ICON_ARROW_RIGHT =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>';

  const pageEl = document.getElementById("page-practice");

  let session = null;        // 当前会话（currentSession）
  let perPage = 10;
  let totalPages = 1;
  let currentPage = 1;
  let timed = false;         // 是否限时
  let limitSeconds = 0;
  let submitting = false;
  let timerId = null;
  let advanceTimerId = null; // 自动跳题延时器
  let pageInputs = [];       // 当前页的输入框（按题序）
  let built = false;

  const els = {};

  /* ---------- 工具 ---------- */

  /** 秒 → "mm:ss"（分钟数超 99 时不补零） */
  function fmtClock(totalSeconds) {
    const s = Math.max(0, Math.floor(totalSeconds));
    const mm = Math.floor(s / 60);
    const ss = s % 60;
    return (mm < 10 ? "0" + mm : String(mm)) + ":" + (ss < 10 ? "0" + ss : String(ss));
  }

  /** 秒 → "X分Y秒" / "X小时Y分Z秒"（结果页也用） */
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

  /** 解析作答字符串：合法整数返回 Number，空/半截（如 "-"）返回 null */
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
    let digits = raw.replace(/[^0-9]/g, "").replace(/^0+(?=\d)/, "");
    return (negative ? "-" : "") + digits;
  }

  function elapsedSeconds() {
    const start = typeof CS.state.startedAt === "number" ? CS.state.startedAt : Date.now();
    return Math.max(0, (Date.now() - start) / 1000);
  }

  /* ---------- 骨架 ---------- */

  function buildSkeleton() {
    if (built || !pageEl) {
      return;
    }
    pageEl.innerHTML =
      '<div class="practice-topbar">' +
      '  <div class="practice-heading">' +
      '    <h2 class="practice-title"><span class="practice-title-icon">' + ICON_STAR + "</span>快来答题吧！</h2>" +
      '    <p class="practice-progress"></p>' +
      "  </div>" +
      '  <div class="timer-pill" role="timer" aria-label="练习计时">' +
      '    <span class="timer-icon">' + ICON_CLOCK + "</span>" +
      '    <span class="timer-text">00:00</span>' +
      "  </div>" +
      "</div>" +
      '<div class="practice-body">' +
      '  <div class="question-grid"></div>' +
      '  <div class="pagination-bar">' +
      '    <button type="button" class="page-btn page-prev">' + ICON_ARROW_LEFT + "<span>上一页</span></button>" +
      '    <span class="page-indicator"></span>' +
      '    <button type="button" class="page-btn page-next"><span>下一页</span>' + ICON_ARROW_RIGHT + "</button>" +
      "  </div>" +
      '  <div class="practice-footer">' +
      '    <button type="button" class="btn-primary submit-btn"><span class="btn-label">提交练习</span>' + ICON_STAR + "</button>" +
      '    <p class="practice-tip">写完记得点「提交练习」哦！</p>' +
      "  </div>" +
      "</div>" +
      '<div class="empty-hint hidden">还没有练习哦，先回首页开始一局吧！</div>';

    els.topbar = pageEl.querySelector(".practice-topbar");
    els.progress = pageEl.querySelector(".practice-progress");
    els.timerPill = pageEl.querySelector(".timer-pill");
    els.timerText = pageEl.querySelector(".timer-text");
    els.body = pageEl.querySelector(".practice-body");
    els.grid = pageEl.querySelector(".question-grid");
    els.paginationBar = pageEl.querySelector(".pagination-bar");
    els.prevBtn = pageEl.querySelector(".page-prev");
    els.nextBtn = pageEl.querySelector(".page-next");
    els.indicator = pageEl.querySelector(".page-indicator");
    els.submitBtn = pageEl.querySelector(".submit-btn");
    els.submitLabel = pageEl.querySelector(".submit-btn .btn-label");
    els.emptyHint = pageEl.querySelector(".empty-hint");

    els.prevBtn.addEventListener("click", function () {
      gotoPage(currentPage - 1, false);
    });
    els.nextBtn.addEventListener("click", function () {
      gotoPage(currentPage + 1, true);
    });
    els.submitBtn.addEventListener("click", function () {
      doSubmit(false);
    });

    built = true;
  }

  /* ---------- 题目卡片与翻页 ---------- */

  function buildCard(q) {
    const card = document.createElement("div");
    card.className = "question-card";

    const seq = document.createElement("span");
    seq.className = "q-seq";
    seq.textContent = String(q.seq + 1);
    seq.setAttribute("aria-hidden", "true");

    const expr = document.createElement("p");
    expr.className = "q-expression";
    expr.textContent = q.expression + " =";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "q-input";
    input.inputMode = "numeric";
    input.autocomplete = "off";
    input.maxLength = MAX_INPUT_LEN;
    input.dataset.seq = String(q.seq);
    input.setAttribute("aria-label", "第" + (q.seq + 1) + "题答案");
    input.value = String(CS.state.answers[q.seq] == null ? "" : CS.state.answers[q.seq]);

    const index = pageInputs.length;
    pageInputs.push(input);
    refreshAnsweredState(input, card);

    input.addEventListener("input", function () {
      const clean = sanitizeInput(input.value);
      if (clean !== input.value) {
        input.value = clean;
      }
      CS.state.answers[q.seq] = clean;
      refreshAnsweredState(input, card);
      if (parseAnswer(clean) !== null) {
        scheduleAutoAdvance(index);
      } else {
        cancelAutoAdvance();
      }
    });

    input.addEventListener("focus", function () {
      cancelAutoAdvance();
      input.select();
    });

    input.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        cancelAutoAdvance();
        jumpTo(index + 1, true);
      } else if (ev.key === "Backspace" && input.value === "" && index > 0) {
        ev.preventDefault();
        focusInput(index - 1);
      }
    });

    card.appendChild(seq);
    card.appendChild(expr);
    card.appendChild(input);
    return card;
  }

  function refreshAnsweredState(input, card) {
    card.classList.toggle("is-answered", parseAnswer(input.value) !== null);
  }

  function focusInput(index) {
    const input = pageInputs[index];
    if (input) {
      input.focus();
      input.select();
    }
  }

  /** 跳到当前页第 index 个输入；越页则翻页并聚焦首页输入；整卷末尾按需聚焦提交按钮 */
  function jumpTo(index, focusSubmitAtEnd) {
    if (index < pageInputs.length) {
      focusInput(index);
      return;
    }
    if (currentPage < totalPages) {
      gotoPage(currentPage + 1, true);
      return;
    }
    if (focusSubmitAtEnd) {
      els.submitBtn.focus();
    }
  }

  function scheduleAutoAdvance(index) {
    cancelAutoAdvance();
    advanceTimerId = setTimeout(function () {
      advanceTimerId = null;
      jumpTo(index + 1, false);
    }, AUTO_ADVANCE_MS);
  }

  function cancelAutoAdvance() {
    if (advanceTimerId) {
      clearTimeout(advanceTimerId);
      advanceTimerId = null;
    }
  }

  /** 当前页未作答的题号（人类编号）列表 */
  function collectUnanswered(pageNo) {
    const start = (pageNo - 1) * perPage;
    const slice = session.questions.slice(start, start + perPage);
    const missing = [];
    slice.forEach(function (q) {
      if (parseAnswer(CS.state.answers[q.seq]) === null) {
        missing.push(q.seq + 1);
      }
    });
    return missing;
  }

  function gotoPage(target, focusFirst) {
    if (!session || submitting) {
      return;
    }
    const clamped = Math.min(Math.max(1, target), totalPages);
    if (clamped === currentPage) {
      return;
    }
    cancelAutoAdvance();

    const missing = collectUnanswered(currentPage);
    if (missing.length > 0) {
      CS.toast.info("第 " + missing.join("、") + " 题还没写答案哦！");
    }

    currentPage = clamped;
    renderPage(focusFirst);
  }

  function renderPage(focusFirst) {
    cancelAutoAdvance();
    pageInputs = [];
    els.grid.innerHTML = "";

    const start = (currentPage - 1) * perPage;
    const frag = document.createDocumentFragment();
    session.questions.slice(start, start + perPage).forEach(function (q) {
      frag.appendChild(buildCard(q));
    });
    els.grid.appendChild(frag);

    els.indicator.textContent = currentPage + " / " + totalPages;
    els.progress.textContent =
      "第 " + currentPage + " / " + totalPages + " 页 · 共 " + session.questions.length + " 题";
    els.prevBtn.disabled = currentPage <= 1;
    els.nextBtn.disabled = currentPage >= totalPages;
    els.paginationBar.classList.toggle("hidden", totalPages <= 1);

    if (focusFirst && pageInputs.length > 0) {
      pageInputs[0].focus();
    }
  }

  /* ---------- 计时器 ---------- */

  function startTimer() {
    stopTimer();
    updateTimer();
    timerId = setInterval(updateTimer, TICK_MS);
  }

  function stopTimer() {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
    els.timerPill.classList.remove("is-urgent");
  }

  function updateTimer() {
    if (!timed) {
      els.timerText.textContent = fmtClock(elapsedSeconds());
      return;
    }
    const remain = limitSeconds - elapsedSeconds();
    if (remain <= 0) {
      els.timerText.textContent = "00:00";
      els.timerPill.classList.remove("is-urgent");
      stopTimer();
      autoSubmit();
      return;
    }
    els.timerText.textContent = fmtClock(Math.ceil(remain));
    els.timerPill.classList.toggle("is-urgent", remain <= URGENT_SECONDS);
  }

  /* ---------- 提交 ---------- */

  function autoSubmit() {
    if (submitting || !session) {
      return;
    }
    CS.toast.info("时间到啦，自动提交咯！");
    doSubmit(true);
  }

  async function doSubmit(timedOut) {
    if (submitting || !session) {
      return;
    }
    submitting = true;
    cancelAutoAdvance();
    els.submitBtn.disabled = true;
    els.submitLabel.textContent = "提交中…";

    // 全量收集作答：未作答的题传 null（后端按未作答计）
    const answers = {};
    let missingCount = 0;
    session.questions.forEach(function (q) {
      const value = parseAnswer(CS.state.answers[q.seq]);
      if (value === null) {
        missingCount += 1;
      }
      answers[String(q.seq)] = value;
    });
    if (!timedOut && missingCount > 0) {
      CS.toast.info("还有 " + missingCount + " 题没写答案哦，会按未作答提交");
    }

    const elapsed = Math.round(elapsedSeconds() * 10) / 10;
    try {
      const result = await CS.api.callBridge("submit_practice", {
        session_id: session.session_id,
        answers: answers,
        duration_seconds: elapsed
      });
      stopTimer();
      CS.state.practice = {
        sessionId: session.session_id,
        result: result,
        elapsedSeconds: elapsed,
        timedOut: !!timedOut
      };
      CS.router.showPage("page-result");
    } catch (err) {
      CS.toast.error(err && err.message ? err.message : "提交失败，请重试");
    } finally {
      submitting = false;
      els.submitBtn.disabled = false;
      els.submitLabel.textContent = "提交练习";
    }
  }

  /* ---------- 激活 / 休眠（配合 router 切页） ---------- */

  function showEmpty() {
    stopTimer();
    cancelAutoAdvance();
    els.body.classList.add("hidden");
    els.topbar.classList.add("hidden");
    els.emptyHint.classList.remove("hidden");
  }

  function activate() {
    if (!pageEl || !pageEl.classList.contains("active")) {
      return;
    }
    buildSkeleton();

    const s = CS.state.currentSession;
    if (!s || !Array.isArray(s.questions) || s.questions.length === 0) {
      showEmpty();
      return;
    }

    const isNew = !session || session.session_id !== s.session_id;
    session = s;
    perPage = Math.max(1, Number(s.per_page) ||
      Number(CS.state.config && CS.state.config.per_page) || 10);
    totalPages = Math.max(1, Number(s.total_pages) ||
      Math.ceil(session.questions.length / perPage));
    limitSeconds = s.duration_seconds == null ? 0 : Number(s.duration_seconds) || 0;
    timed = limitSeconds > 0;

    if (isNew) {
      currentPage = 1;
      if (!CS.state.answers || typeof CS.state.answers !== "object") {
        CS.state.answers = {};
      }
    }
    currentPage = Math.min(Math.max(1, currentPage), totalPages);

    els.emptyHint.classList.add("hidden");
    els.topbar.classList.remove("hidden");
    els.body.classList.remove("hidden");

    renderPage(isNew);
    startTimer();
  }

  function deactivate() {
    stopTimer();
    cancelAutoAdvance();
  }

  function init() {
    if (!pageEl) {
      return;
    }
    buildSkeleton();
    // 监听 router 对页面容器的 active 类切换（不修改 router.js）
    const observer = new MutationObserver(function () {
      if (pageEl.classList.contains("active")) {
        activate();
      } else {
        deactivate();
      }
    });
    observer.observe(pageEl, { attributes: true, attributeFilter: ["class"] });
  }

  init();

  return {
    activate: activate,
    deactivate: deactivate,
    doSubmit: doSubmit
  };
})();
