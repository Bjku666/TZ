# 视频原版五日线回踩隔日超短交易纪律系统

本仓库只保留一套策略：视频原版“五日线回踩隔日超短”。系统负责生成正式收盘批次、跨日候选、盘中 MA5 回踩信号、人工交易记录、T+1 持仓提醒、费用和复盘审计；不连接券商，不自动下单。

## 核心规则

- 正式初筛从全市场原始成交额前 20 开始，先取原始榜，再过滤创业板、科创板、北交所、ST、退市、停牌或无有效价格股票。
- 过滤后不足 20 只时不从第 21 名以后补位。
- `000725 京东方A` 不特殊排除。
- 入选日收盘价必须大于等于入选日 `MA5 close`。
- 入选当天不能买，`eligible_from` 为下一交易日。
- 候选从下一交易日起跨日等待 MA5 回踩，不设置任意过期天数。
- 盘中 MA5 使用“前 4 个完成交易日收盘价 + 当前实时价格”计算。
- 回踩工程容差为 `±0.5%`，属于测量口径，不是视频新增选股条件。
- 买入时间为 `09:30 <= t < 10:00` 和 `14:30 <= t < 15:00`。
- 买入后按隔日超短管理，下一交易日早盘观察，10 点前不能涨停则提示卖出；用户可显式选择延迟至 14:30 后处理。

## 规则边界

- 视频原版信号：正式前 20、入选日站上 MA5、跨日等待回踩、视频买入时段、隔日卖出提醒。
- 执行约束：100 股整数倍、现金、T+1、可卖数量、停牌、费用、人工确认。
- 工程口径：MA5 触线容差、行情新鲜度、10 点涨停后最小补全。

大盘、板块、MA10、MA20、浮亏风险只作为辅助信息展示，不参与初筛、观察、待买分组和买入违规审计。

## 数据模型

SQLite 新增并维护：

- `schema_migrations`
- `selection_batches`
- `selection_items`
- `candidate_cycles`
- `candidate_events`
- `signal_events`

`data/watchlist.csv` 仅作为兼容导出和展示缓存，不再是候选生命周期的唯一权威数据。

## 本地运行

```bash
./启动强势回踩系统.command
```

后端默认 `http://127.0.0.1:8000`，前端默认 `http://127.0.0.1:5173`。

## 验证

```bash
PYTHONPATH=. .venv/bin/pytest -q
npm --prefix frontend run lint
npm --prefix frontend run build
```

## 文档

- `docs/VIDEO_ORIGINAL_RULES.md`
- `docs/RULE_BOUNDARIES.md`
- `docs/CANDIDATE_STATE_MACHINE.md`
- `docs/DATA_MODEL.md`
- `docs/MIGRATION_REPORT.md`
- `docs/TEST_REPORT.md`
