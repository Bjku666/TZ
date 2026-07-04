# 候选状态机

统一状态枚举：

```text
INITIAL_SCREENED
INITIAL_REJECTED
WAITING_ELIGIBLE_DATE
OBSERVING
IN_TOUCH_ZONE_OUTSIDE_WINDOW
BUY_READY
BELOW_MA5
BOUGHT
NEXT_DAY_OBSERVING
MORNING_EXIT_DUE
DEFERRED_TO_AFTERNOON
AFTERNOON_EXIT_DUE
LIMIT_UP_HOLD
CLOSED
INVALIDATED
CANCELLED
```

主流程：

```text
正式初筛
→ 入选日收盘站上MA5
→ 等待下一交易日
→ 跨日观察
→ 买入时段进入MA5回踩区
→ 当前待买
→ 人工记录买入
→ 次日卖出管理
→ 已完成
```

失效流程：

- 买入前某个完成交易日收盘价低于当日 MA5，候选进入 `INVALIDATED`。
- 用户手动取消进入 `CANCELLED`。
- 买入窗口结束仍未买入，`BUY_READY` 回到 `OBSERVING`。

所有状态变化写入 `candidate_events`。

