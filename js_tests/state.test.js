"use strict";

const { reset, load } = require("./support");

test("共享状态初始字段完整且为空", function () {
  reset();
  load("state.js");

  expect(window.CS.state).toEqual({
    currentSession: null,
    config: null,
    answers: {},
    startedAt: null
  });
});

test("共享状态是同一对象，页面模块读写互相可见", function () {
  reset();
  load("state.js");

  const state = window.CS.state;
  state.currentSession = { session_id: "s1" };
  state.answers[0] = "-3";

  expect(CS.state).toBe(state);
  expect(window.CS.state.currentSession.session_id).toBe("s1");
  expect(window.CS.state.answers[0]).toBe("-3");
});
