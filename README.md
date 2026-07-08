# TZ 五日线回踩交易纪律工作台

TZ 是与同花顺配合使用的个人交易纪律与复盘工作台。它不做全市场选股、不提供实时荐股、不连接券商，也不自动下单。

同花顺负责行情、股票选择和真实下单；TZ 负责：

- 模拟训练与实盘记录两套完全独立的账户账本；
- 人工登记买入、卖出和历史成交；
- T+1 可卖数量、现金、100 股整数倍和买入时段校验；
- 当前持仓、10:00 行动节点、延迟至 14:30 尾盘处理；
- 手续费、印花税、过户费和累计盈亏重算；
- 通知、持仓备注、同花顺期末数手工对账；
- 计划、执行、结果、下一步四段式复盘。

## 产品结构

一级页面只保留四个：

1. **今日执行**：账户概览、今日待办、成交记录和违规提醒。
2. **当前持仓**：持仓数量、可卖数量、T+1 锁定和行动状态。
3. **交易记录**：当前账户的完整流水、编辑、删除和费用重算。
4. **复盘分析**：统计指标与四段式有效复盘。

设置与通知通过顶部抽屉打开，不占用一级页面。

## 账户隔离

所有业务数据都以 `mode` 为强制分区键：

- `simulation`：模拟训练账户；
- `real`：实盘记录账户。

交易、持仓推导、现金、费用设置、对账数字、延迟决定、备注、通知和复盘均不会跨账户读取或修改。共享内容只包括程序代码和规则定义。

## 本地运行

### 1. 后端

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. 前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：

```text
http://127.0.0.1:5173
```

Vite 会把 `/api` 请求代理到 `http://127.0.0.1:8000`。

## 测试

```bash
python -m pytest
cd frontend
npm install
npm run lint
npm run build
```

## 数据文件

SQLite 默认写入：

```text
data/tz_workspace.sqlite3
```

可以通过环境变量 `TZ_DATA_DIR` 更改数据目录。数据库文件不会提交到 GitHub。

## 核心 API

```text
GET    /api/accounts/{mode}/workspace
POST   /api/accounts/{mode}/refresh

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

旧的选股、候选池、盘中扫描、行情抓取、股票池和荐股 API 不再存在。
