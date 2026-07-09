# TZ 多交易模式纪律工作台

TZ 是与同花顺配合使用的个人交易纪律、账户记录和复盘工作台。默认内置“五日线回踩”模式，并预留“模式2”“模式3”的规则框架。它不做全市场选股、不提供实时荐股、不连接券商，也不自动下单。

同花顺负责行情、股票选择和真实下单；TZ 负责：

- 模拟训练与实盘记录两套完全独立的账户账本；
- 五日线回踩、模式2、模式3 三套交易模式分区；
- 人工登记买入、卖出和历史成交；
- T+1 可卖数量、现金、100 股整数倍和当前交易模式规则校验；
- 当前持仓、行动节点、延后处理和策略状态提醒；
- 手续费、印花税、过户费和累计盈亏重算；
- 资金变化、已实现/浮动盈亏、费用和资产曲线复盘；
- 通知、持仓备注、同花顺期末数手工对账；
- 计划、执行、结果、下一步四段式复盘。

## 产品结构

一级页面只保留四个：

1. **今日执行**：账户概览、资金变化、今日待办、成交摘要和违规提醒。
2. **当前持仓**：持仓表格/卡片、可卖数量、T+1 锁定、行动状态和详情面板。
3. **交易记录**：当前账户完整流水、筛选、编辑、删除、费用重算和审计标签。
4. **复盘分析**：核心指标、资金/盈亏变化、纪律分析和四段式有效复盘。

设置与通知通过顶部抽屉打开，不占用一级页面。

## 账户与交易模式隔离

所有业务数据都以 `mode + strategy_id` 为强制分区键。

`mode` 表示账户：

- `simulation`：模拟训练账户；
- `real`：实盘记录账户。

`strategy_id` 表示交易模式：

- `ma5_pullback`：五日线回踩，承接当前系统原有规则；
- `mode2`：模式2，规则名称与细则待配置；
- `mode3`：模式3，规则名称与细则待配置。

交易、持仓推导、延后决定、备注、通知和复盘均不会跨账户或交易模式读取或修改。账户本金、手续费、行情和对账设置仍按模拟/实盘账户保存。

## 本地运行

```bash
./启动TZ纪律工作台.command
```

后端默认 `http://127.0.0.1:8001`，前端默认 `http://127.0.0.1:5174`。

也可以手动启动：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001
```

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

## 验证

```bash
python -m pytest tests/test_workspace.py
npm --prefix frontend run lint
npm --prefix frontend run build
```

## 核心 API

```text
GET    /api/accounts/{mode}/workspace
POST   /api/accounts/{mode}/refresh
GET    /api/accounts/{mode}/strategies

POST   /api/accounts/{mode}/trades
PUT    /api/accounts/{mode}/trades/{trade_id}
DELETE /api/accounts/{mode}/trades/{trade_id}
POST   /api/accounts/{mode}/trades/recalculate-fees

POST   /api/accounts/{mode}/positions/{code}/defer-exit
DELETE /api/accounts/{mode}/positions/{code}/defer-exit
POST   /api/accounts/{mode}/positions/{code}/notes

GET    /api/accounts/{mode}/settings
PUT    /api/accounts/{mode}/settings

GET    /api/accounts/{mode}/reviews
POST   /api/accounts/{mode}/reviews

PUT    /api/accounts/{mode}/notifications/{id}/read
POST   /api/accounts/{mode}/notifications/read-all
DELETE /api/accounts/{mode}/notifications
```

所有工作区、交易、持仓、复盘和通知接口都支持可选查询参数 `?strategy=mode2` 或 `?strategy=mode3`；不传时默认使用 `ma5_pullback`，兼容旧调用。

旧的选股、候选池、盘中扫描、行情抓取、股票池和荐股 API 不再存在。
