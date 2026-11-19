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
  startedAt: null,

  /** 练习结果页数据（result.js 写入） */
  practice: null,

  /** 历史记录列表缓存（history.js 读写） */
  historyCache: null,
  /** 历史记录缓存失效标记（result.js 置位，history.js 消费） */
  historyCacheDirty: false,

  /** 错题本列表缓存（wrongbook.js 读写） */
  wrongBookCache: null,
  /** 错题本缓存失效标记（result.js 置位，wrongbook.js 消费） */
  wrongBookCacheDirty: false
};
