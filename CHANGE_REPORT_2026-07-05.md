# 持仓与盘中刷新优化变更报告

## 根因

1. 运行在 `127.0.0.1:8000` 的 uvicorn 是旧进程。旧健康检查没有提交号和服务时间，OpenAPI 也没有 K 线任务接口。
2. 后端把行情日期、交易结算日期和用户操作日期合并成一个 `asOfDate`。
3. 前端用 `availableQuantity <= 0` 推断“今日建仓”和“T+1锁仓”，导致休市、同步异常和真实 T+1 状态混淆。
4. 行情刷新同步抓取全市场指数、行业和个股行业映射，完成后前端又串行执行完整 `loadAllData()`。

## 数据结构变化

持仓新增：

```text
operationDate
valuationDate
isTodayBuy
todayBuyQuantity
settledQuantity
availableQuantity
t1LockedQuantity
isT1Locked
nextSellableTradeDate
nextActionTime
marketPhase
canExecuteSellNow
sellBlockedReason
calendarDegraded
```

健康检查新增：

```text
gitCommit
buildTime
serverTime
timezone
```

行情快路径新增：

```text
requestId
serverTime
source
isStale
dataAgeSeconds
durationMs
watchlist
positions
accountState
sourceHealth
```

## 主要修改

- 新增上海时区、本地缓存优先的交易日历模块；无缓存时按工作日降级并显式返回 `calendarDegraded=true`。
- 按买入批次重建持仓，卖出优先消耗旧批次，支持“旧仓可卖 + 今日加仓锁定”。
- 后端统一生成交易状态和卖出阻断原因；前端不再从可卖数量猜测买入日期。
- 前端持仓计划、卖出入口和活动日志改用后端明确字段。
- 初始核心接口并行加载，报告数据只在复盘页加载。
- 30 秒行情刷新直接消费组合响应，不再刷新后调用完整 `loadAllData()`。
- 行情刷新增加 5 秒前端超时、响应序号保护、前后端 single-flight、缓存保留和数据新鲜度展示。
- 页面隐藏时暂停自动刷新；回到可见且处于交易时段时立即刷新。
- 市场/行业上下文改为 stale-while-revalidate，不再阻塞行情快路径。
- 行情源增加连续失败计数、延迟统计和 60 秒熔断冷却。
- 股票池重建、异动扫描和行情刷新分别使用互斥锁。
- K 线补齐改为后台任务，四线程受限并发，前端展示完成进度。

## 验收结果

`600176` 在 `operationDate=2026-07-04` 时实测：

```text
buyDate=2026-07-03
valuationDate=2026-07-03
isTodayBuy=false
availableQuantity=0
t1LockedQuantity=100
nextSellableTradeDate=2026-07-06
marketPhase=weekend
canExecuteSellNow=false
sellBlockedReason=休市，下一交易日 2026-07-06 可处理
```

旧进程重启后，健康检查返回提交 `048bd2c`，新 OpenAPI 已包含 K 线任务接口。

## 测试与性能

- `pytest`: 34 passed。
- TypeScript 检查：通过。
- Vite production build：通过。
- 30 只当前池行情快路径单次实测：后端 `durationMs=946`，墙钟时间约 0.85 秒。
- 2026-07-04 持仓接口本地响应：约 0.06 秒。

## 当前降级限制

- 本地尚无完整法定节假日缓存，因此当前明确标记 `calendarDegraded=true`，周末判断准确，法定调休依赖后续导入缓存。
- 股票池重建已有 single-flight、旧池保留和原子替换，但阶段进度仍是同步请求内的粗粒度状态，尚未改成独立任务查询接口。
- 性能数据是本机单次实测，不等同于长期 P95；日志字段已加入，需积累样本后统计。
