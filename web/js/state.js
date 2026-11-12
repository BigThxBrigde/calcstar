"use strict";

/* CalcStar 前端共享状态（内存对象） */
window.CS = window.CS || {};

CS.state = {
  /** 当前练习会话：create_practice 返回的数据（session_id/questions/分页元数据等） */
  currentSession: null,

  /** 当前练习使用的配置（与后端约定一致的参数对象） */
  config: null,

  /** 用户作答：seq -> 答案（练习页使用，后续任务读写） */
  answers: {},

  /** 练习开始时间戳（毫秒），用于计算用时 */
  startedAt: null
};
