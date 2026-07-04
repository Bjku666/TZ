# 测试报告

## Python

命令：

```bash
PYTHONPATH=. .venv/bin/pytest -q
```

结果：

```text
90 passed, 4 warnings
```

覆盖重点：

- 股票范围和京东方A。
- 原始前 20 后过滤且不补位。
- 入选日 MA5。
- D+1 和周末跨日。
- 买入窗口边界。
- MA5 触线容差。
- 过期行情不产生买点。
- 资金不足不取消原版信号。
- 历史补录审计。
- 隔日卖出状态。
- 数据库迁移可重复执行。

## TypeScript

命令：

```bash
npm --prefix frontend run lint
```

结果：通过。

## 前端构建

命令：

```bash
npm --prefix frontend run build
```

结果：通过。

## 关键接口实测

临时后端端口：`127.0.0.1:8001`

```text
/api/health                       200 20.53 ms
/api/rules                        200 3.97 ms
/api/selection/official/latest    200 112.19 ms
/api/candidates                   200 10.81 ms
/api/portfolio                    200 149.54 ms
/api/trades                       200 20.33 ms
/api/watchlist/refresh-quotes     200 12568.54 ms
```

行情刷新本次走真实行情源链路，东方财富、efinance、AKShare 降级后由新浪行情返回，因此耗时明显超过目标 P95。代码仍保留熔断、缓存和锁；实际交易时段建议固定可用行情源或降低失败源重试等待。
