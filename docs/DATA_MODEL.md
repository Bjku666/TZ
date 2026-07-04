# 数据模型

## SQLite 表

### schema_migrations

记录幂等迁移版本。

### selection_batches

正式批次和盘中预览批次的元数据：

```text
id, selection_date, generated_at, data_as_of, source,
is_official, raw_top_n, status, source_message,
created_at, updated_at
```

### selection_items

原始前 20 中每只股票的筛选结果：

```text
id, batch_id, code, name, raw_rank, turnover,
close_price, ma5_close, market_allowed, exclusion_reason,
above_ma5, candidate_created, created_at
```

### candidate_cycles

跨日候选生命周期：

```text
id, code, name, source_batch_id, selection_date, eligible_from,
state, waiting_trade_days, last_close, last_ma5_close,
last_live_price, last_ma5_live, last_deviation,
touch_started_at, touch_detected_at, bought_trade_id,
invalidated_at, invalidated_reason, closed_at, created_at, updated_at
```

同一代码最多一个未完成活跃候选周期。

### candidate_events

候选事件流水，不覆盖历史。

### signal_events

视频信号和执行状态流水，用于统计“信号成立但未能执行”的情况。

## CSV 兼容

`data/watchlist.csv` 继续存在，但只是派生展示缓存，不再是候选生命周期权威。

