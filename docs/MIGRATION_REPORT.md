# 迁移报告

## 备份位置

本次执行备份目录：

```text
data/backups/video_original_migration_20260705_014902
```

包含：

- `watchlist.csv`
- `holdings.csv`
- `trades/`
- `app.db`
- `settings.json`
- `reports/`

## 迁移原则

- 保留历史交易、持仓、报告和设置。
- 旧 watchlist 不作为新视频原版有效候选。
- 旧交易快照继续可查看。
- 新候选从第一次新正式前 20 批次开始。
- SQLite 迁移可重复执行。

## 新增表

- `schema_migrations`
- `selection_batches`
- `selection_items`
- `candidate_cycles`
- `candidate_events`
- `signal_events`

## 旧规则处理

增强版条件已从规则内核、后端分组、买入审计和新前端展示中移除。文档中保留这些名称只用于说明“已删除”。

`data/watchlist.csv` 已在备份后重置为空派生缓存，避免旧增强版导入池被当成新视频原版候选。新候选必须来自 SQLite 正式批次。

## 回滚说明

1. 停止后端和前端。
2. 从备份目录复制 `app.db`、`watchlist.csv`、`holdings.csv`、`trades/`、`settings.json`、`reports/` 覆盖回 `data/`。
3. 重启系统。
