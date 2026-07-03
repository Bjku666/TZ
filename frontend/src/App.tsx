import { useState, useEffect } from "react";
import { 
  Activity, 
  Briefcase, 
  TrendingUp, 
  History, 
  FileText, 
  Settings, 
  RefreshCw, 
  Download, 
  Plus, 
  Trash2, 
  Search, 
  Eye, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Calendar, 
  Info, 
  BookOpen, 
  FileSpreadsheet, 
  ShieldAlert,
  ChevronRight,
  Sparkles,
  Coins,
  Edit
} from "lucide-react";
import KLineChart from "./components/KLineChart";
import { Stock, TradeLog, StockGroup, StockStage, Position, AccountState, ReviewReport } from "./types";

function isMainBoard(code: string): boolean {
  if (!code) return false;
  if (code === "000725") return false;
  if (code.startsWith("600") || code.startsWith("601") || code.startsWith("603") || code.startsWith("605")) {
    return true;
  }
  if (code.startsWith("000") || code.startsWith("001") || code.startsWith("002")) {
    return true;
  }
  return false;
}

export default function App() {
  // 核心应用状态
  const [activeTab, setActiveTab] = useState<"dashboard" | "watchlist" | "intraday" | "trades" | "review" | "settings">("dashboard");
  const [accountState, setAccountState] = useState<AccountState>({
    initialCash: 100000,
    availableCash: 100000,
    holdingValue: 0,
    totalAssets: 100000,
    realizedPnL: 0,
    floatingPnL: 0,
    totalPnL: 0,
    totalReturnPct: 0
  });
  const [positions, setPositions] = useState<Position[]>([]);
  const [watchlist, setWatchlist] = useState<Stock[]>([]);
  const [trades, setTrades] = useState<TradeLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLog, setActionLog] = useState<string[]>([]);
  const [currentMode, setCurrentMode] = useState<"simulation" | "real">("simulation");

  // 筛选与交互状态
  const [watchlistGroup, setWatchlistGroup] = useState<StockGroup>("初筛");
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // 交易确认模态框状态
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [tradeTarget, setTradeTarget] = useState<Stock | null>(null);
  const [tradeType, setTradeType] = useState<"BUY" | "SELL">("BUY");
  const [tradePrice, setTradePrice] = useState(0);
  const [tradeQuantity, setTradeQuantity] = useState(100);
  const [tradeReason, setTradeReason] = useState("");
  const [tradeRemark, setTradeRemark] = useState("");

  // 复盘报告相关状态
  const [reviewType, setReviewType] = useState<"daily" | "weekly" | "monthly">("daily");
  const [reportsList, setReportsList] = useState<ReviewReport[]>([]);
  const [auditStats, setAuditStats] = useState<any>(null);
  const [reportSummary, setReportSummary] = useState("");
  const [reportPlan, setReportPlan] = useState("");
  const [reportDate, setReportDate] = useState(new Date().toISOString().split("T")[0]);

  // 标准化多维度复盘工作台状态
  const [shTrend, setShTrend] = useState("向上");
  const [shVolume, setShVolume] = useState("放量");
  const [shFlow, setShFlow] = useState("净流入");
  const [szTrend, setSzTrend] = useState("向上");
  const [szVolume, setSzVolume] = useState("放量");
  const [szFlow, setSzFlow] = useState("净流入");
  const [cyTrend, setCyTrend] = useState("向上");
  const [cyVolume, setCyVolume] = useState("放量");
  const [cyFlow, setCyFlow] = useState("净流入");
  const [systemicRisk, setSystemicRisk] = useState(false);

  const [reviewedEtfCount, setReviewedEtfCount] = useState(50);
  const [hotSectors, setHotSectors] = useState("");
  const [etfFlowNotes, setEtfFlowNotes] = useState("");

  const [top200Reviewed, setTop200Reviewed] = useState(false);
  const [volRatioReviewed, setVolRatioReviewed] = useState(false);
  const [limitUpReviewed, setLimitUpReviewed] = useState(false);
  const [diagnosedHoldings, setDiagnosedHoldings] = useState<Array<{ code: string; name: string; judgment: string; actionPlan: string }>>([]);

  const [sellCompliant, setSellCompliant] = useState("符合模式");
  const [profitExperience, setProfitExperience] = useState("");
  const [lossAnalysis, setLossAnalysis] = useState("");

  // 交易费用配置 state
  const [feeSettings, setFeeSettings] = useState({
    commissionRate: 0.0003,
    minCommission: 5.0,
    stampDutyRate: 0.0005,
    transferFeeRate: 0.00001
  });

  // 5个复盘视图状态与聚合数据 state
  const [activeReviewSubTab, setActiveReviewSubTab] = useState<"today" | "market" | "sector" | "stock" | "action">("today");
  const [reportContext, setReportContext] = useState<any>(null);

  // 编辑单笔交易记录状态
  const [editingTrade, setEditingTrade] = useState<TradeLog | null>(null);
  const [editPrice, setEditPrice] = useState(0);
  const [editQuantity, setEditQuantity] = useState(100);
  const [editDate, setEditDate] = useState("");
  const [editTime, setEditTime] = useState("");
  const [editReason, setEditReason] = useState("");
  const [editRemark, setEditRemark] = useState("");
  const [editCommission, setEditCommission] = useState(0);
  const [editStampDuty, setEditStampDuty] = useState(0);
  const [editTransferFee, setEditTransferFee] = useState(0);
  const [editRulesConclusion, setEditRulesConclusion] = useState("");
  const [editViolationTags, setEditViolationTags] = useState<string[]>([]);

  // 同花顺表格导入状态
  const [showImportPanel, setShowImportPanel] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [autoFetchHistoryAfterImport, setAutoFetchHistoryAfterImport] = useState(true);

  // 实时系统时钟
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // 当持仓发生变化时，自动初始化或保持个股诊断列表
  useEffect(() => {
    if (positions.length > 0) {
      setDiagnosedHoldings(prev => {
        const newDiagnoses = positions.map(pos => {
          const existing = prev.find(p => p.code === pos.code);
          return existing || {
            code: pos.code,
            name: pos.name,
            judgment: "第三方客观评估：买点完好，纪律持有",
            actionPlan: "5日线之上安全运行，暂无变动"
          };
        });
        return newDiagnoses;
      });
    } else {
      setDiagnosedHoldings([]);
    }
  }, [positions]);

  // 加载初始设置
  const loadSettings = async () => {
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const settings = await res.json();
        setCurrentMode(settings.currentMode || "simulation");
        setFeeSettings({
          commissionRate: settings.commissionRate !== undefined ? settings.commissionRate : 0.0003,
          minCommission: settings.minCommission !== undefined ? settings.minCommission : 5.0,
          stampDutyRate: settings.stampDutyRate !== undefined ? settings.stampDutyRate : 0.0005,
          transferFeeRate: settings.transferFeeRate !== undefined ? settings.transferFeeRate : 0.00001
        });
      }
    } catch (err) {
      console.error("加载设置失败:", err);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  // 切换运行模式
  const handleToggleMode = async (mode: "simulation" | "real") => {
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentMode: mode })
      });
      if (res.ok) {
        setCurrentMode(mode);
        logAction(`🔄 运行模式已切换至: ${mode === "simulation" ? "模拟训练" : "实盘记录"}`);
      }
    } catch (err) {
      logAction("❌ 切换运行模式失败");
    }
  };

  // 加载系统所有数据
  const loadAllData = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      // 1. 获取持仓与资产
      const resPortfolio = await fetch(`/api/portfolio?mode=${currentMode}`);
      if (resPortfolio.ok) {
        const data = await resPortfolio.json();
        setAccountState(data.accountState);
        setPositions(data.positions);
      }
      
      // 2. 获取自选池
      const resWatchlist = await fetch("/api/watchlist");
      if (resWatchlist.ok) {
        const data = await resWatchlist.json();
        setWatchlist(data.list);
        // 如果没有选中的股票，默认选当前视图的第一只
        if (data.list.length > 0 && !selectedStock) {
          const firstVisible = firstStockForGroup(data.list, watchlistGroup);
          if (firstVisible) setSelectedStock(firstVisible);
        }
      }

      // 3. 获取交易历史
      const resTrades = await fetch(`/api/trades?mode=${currentMode}`);
      if (resTrades.ok) {
        const data = await resTrades.json();
        setTrades(data.list);
      }

      // 4. 获取复盘审计
      const resAudit = await fetch(`/api/reports/audit?mode=${currentMode}`);
      if (resAudit.ok) {
        const data = await resAudit.json();
        setAuditStats(data);
      }

      // 5. 获取复盘报告列表
      const resReports = await fetch(`/api/reports/list?type=${reviewType}`);
      if (resReports.ok) {
        const data = await resReports.json();
        setReportsList(data.reports);
      }

      // 6. 获取复盘报告聚合数据上下文
      const resContext = await fetch(`/api/reports/context?mode=${currentMode}`);
      if (resContext.ok) {
        const data = await resContext.json();
        setReportContext(data);
      }

    } catch (err) {
      console.error("加载数据错误:", err);
      logAction("❌ 数据加载发生异常，请检查后台连接");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, [watchlistGroup, reviewType, currentMode, activeTab]);

  const logAction = (msg: string) => {
    const timestamp = new Date().toTimeString().split(" ")[0];
    setActionLog(prev => [`[${timestamp}] ${msg}`, ...prev.slice(0, 49)]);
  };

  // 生成股票池
  const handleGenerateStockPool = async () => {
    setLoading(true);
    logAction("⏳ 正在拉取主板成交额排行并执行纪律筛选...");
    try {
      const res = await fetch("/api/watchlist/generate", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data.list);
        logAction(`✅ 股票池自动构建完毕！已过滤ST、创业板、科创板、北交所、京东方A等笨重股。当前初筛数量: ${data.list.length} 只`);
        setActiveTab("watchlist");
        setWatchlistGroup("初筛");
        if (data.list.length > 0) {
          setSelectedStock(data.list[0]);
        }
        // 自动触发一次补充历史K线的通知
        logAction("💡 提示: 初筛股票可能缺少K线计算指标，可点击「一键补充K线」进行指标加载");
      } else {
        throw new Error();
      }
    } catch (err) {
      logAction("❌ 自动股票池生成失败，请稍后重试");
    } finally {
      setLoading(false);
      loadAllData(true);
    }
  };

  // 盘中轻量刷新
  const handleRefreshQuotes = async () => {
    setLoading(true);
    logAction("⏳ 盘中行情极轻刷新启动...");
    try {
      const res = await fetch("/api/watchlist/refresh-quotes", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data.list);
        logAction("⚡ 盘中现价与MA5偏离率刷新完成！已自动评估买点区间。");
      } else {
        throw new Error();
      }
    } catch (err) {
      logAction("❌ 行情刷新失败，保留本地缓存");
    } finally {
      setLoading(false);
      loadAllData(true);
    }
  };

  // 补充K线历史
  const handleFetchHistory = async (code?: string, fetchAll = false) => {
    setLoading(true);
    logAction(fetchAll ? "⏳ 正在抓取自选池全量历史K线以补齐MA均线指标..." : `⏳ 正在抓取股票 ${code} 的历史K线...`);
    try {
      const res = await fetch("/api/watchlist/fetch-history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, fetchAll })
      });
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data.list);
        logAction(fetchAll ? "✅ 自选股历史数据全部计算并缓存完毕！" : `✅ 股票 ${code} K线补齐完毕，5日均线指标已更新。`);
      } else {
        throw new Error();
      }
    } catch (err) {
      logAction("❌ 历史K线拉取失败，请检查互联网连接");
    } finally {
      setLoading(false);
      loadAllData(true);
    }
  };

  // 记录股票备注
  const handleSaveRemark = async (code: string, remark: string) => {
    try {
      const res = await fetch("/api/watchlist/update-stock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, remark })
      });
      if (res.ok) {
        logAction(`已保存股票 ${code} 的备注`);
        loadAllData(true);
      }
    } catch (err) {
      logAction("❌ 保存备注失败");
    }
  };

  // 打开买入交易模态框
  const openBuyModal = (stock: Stock) => {
    setTradeTarget(stock);
    setTradeType("BUY");
    setTradePrice(stock.price || 10.0);
    setTradeQuantity(100);
    setTradeReason(stockBelongsToGroup(stock, "待买") ? "盘中手动确认：接近5日线并等待回踩不破" : "");
    setTradeRemark("");
    setShowTradeModal(true);
  };

  // 打开卖出交易模态框
  const openSellModal = (pos: Position) => {
    const matched = watchlist.find(s => s.code === pos.code);
    setTradeTarget(matched || {
      code: pos.code,
      name: pos.name,
      price: pos.currentPrice,
      pct: 0, volume: 0, rank: 99, ma5: pos.ma5, ma10: 0, ma20: 0,
      deviation5: pos.deviation5, bigCandlePct: 10, ma5Upward: true, canBuy: false,
      group: "持仓", stage: "等回踩", riskLevel: "normal", reason: "", reminder: "",
      historyStatus: "已有缓存", lastUpdated: "", remark: ""
    });
    setTradeType("SELL");
    setTradePrice(pos.currentPrice || pos.avgCost);
    setTradeQuantity(pos.quantity);
    setTradeReason(pos.currentPrice < pos.ma5 ? "跌破5日线（MA5）执行强制卖出风控止损纪律" : "达到目标，止盈出局");
    setTradeRemark("");
    setShowTradeModal(true);
  };

  // 提交交易记录
  const handleExecuteTrade = async () => {
    if (!tradeTarget) return;
    try {
      const res = await fetch("/api/trades/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: tradeTarget.code,
          name: tradeTarget.name,
          type: tradeType,
          price: Number(tradePrice),
          quantity: Number(tradeQuantity),
          reason: tradeReason,
          remark: tradeRemark,
          mode: currentMode
        })
      });

      if (res.ok) {
        const data = await res.json();
        logAction(`💸 [${currentMode === "real" ? "实盘" : "模拟"}] 交易已存档！${tradeType === "BUY" ? "买入" : "卖出"} ${tradeTarget.name} ${tradeQuantity} 股，审计结论: [${data.trade.rulesConclusion}]`);
        setShowTradeModal(false);
        loadAllData();
      } else {
        const errData = await res.json();
        alert(errData.error || "交易存档失败，请重试");
      }
    } catch (err) {
      logAction("❌ 交易归档通信失败");
    }
  };

  // 删除交易记录
  const handleDeleteTrade = async (id: string) => {
    if (!confirm("确定要删除这笔交易记录吗？持仓与资金将自动回滚重新推导。")) return;
    try {
      const res = await fetch("/api/trades/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, mode: currentMode })
      });
      if (res.ok) {
        logAction(`🗑️ 交易流水 ${id} 已撤销，持仓重新推算中。`);
        loadAllData();
      }
    } catch (err) {
      logAction("❌ 撤销交易失败");
    }
  };

  // 打开编辑交易流水模态框
  const openEditTradeModal = (trade: TradeLog) => {
    setEditingTrade(trade);
    setEditPrice(trade.price);
    setEditQuantity(trade.quantity);
    setEditDate(trade.date);
    setEditTime(trade.time);
    setEditReason(trade.reason);
    setEditRemark(trade.remark || "");
    setEditCommission(trade.commission || 0);
    setEditStampDuty(trade.stampDuty || 0);
    setEditTransferFee(trade.transferFee || 0);
    setEditRulesConclusion(trade.rulesConclusion);
    setEditViolationTags(trade.violationTags || []);
  };

  // 提交修改交易流水
  const handleUpdateTrade = async () => {
    if (!editingTrade) return;
    try {
      const res = await fetch("/api/trades/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: editingTrade.id,
          mode: currentMode,
          price: Number(editPrice),
          quantity: Number(editQuantity),
          date: editDate,
          time: editTime,
          reason: editReason,
          remark: editRemark,
          rulesConclusion: editRulesConclusion,
          violationTags: editViolationTags,
          commission: Number(editCommission),
          stampDuty: Number(editStampDuty),
          transferFee: Number(editTransferFee),
          totalFee: Number((Number(editCommission) + Number(editStampDuty) + Number(editTransferFee)).toFixed(2))
        })
      });

      if (res.ok) {
        logAction(`✍️ 交易流水 ${editingTrade.id} 编辑成功，账单已重新计算并实时同步费用！`);
        setEditingTrade(null);
        loadAllData();
      } else {
        alert("编辑保存失败，请检查输入");
      }
    } catch (err) {
      logAction("❌ 编辑保存通信失败");
    }
  };

  // 保存复盘日报/周报/月报
  const handleSaveReport = async () => {
    if (!reportSummary) {
      alert("请输入复盘心得总结！");
      return;
    }

    // 计算今日买卖数量
    const todayStr = new Date().toISOString().split("T")[0];
    const todayTrades = trades.filter(t => t.date === todayStr);
    const buyCount = todayTrades.filter(t => t.type === "BUY").length;
    const sellCount = todayTrades.filter(t => t.type === "SELL").length;
    const compliantCount = todayTrades.filter(t => t.type === "BUY" && t.rulesConclusion === "符合规则").length;
    const complianceRate = buyCount > 0 ? Number(((compliantCount / buyCount) * 100).toFixed(2)) : 100;

    const newReport: ReviewReport = {
      id: "R" + reviewType + "_" + reportDate,
      type: reviewType,
      date: reportDate,
      buyCount,
      sellCount,
      ruleComplianceRate: complianceRate,
      violations: todayTrades.filter(t => t.rulesConclusion === "违规交易").flatMap(t => t.violationTags),
      realizedPnL: todayTrades.reduce((acc, t) => acc + (t.type === "SELL" ? t.amount - t.totalFee : -(t.amount + t.totalFee)), 0),
      portfolioRisk: positions.filter(p => p.riskLevel === "danger").length > 0 ? "高风险 (部分持仓已破5日线)" : "正常 (持仓均在5日线上方)",
      summary: reportSummary,
      tomorrowPlan: reportPlan,
      createdTime: new Date().toLocaleString(),
      marketAnalysis: {
        shTrend,
        shVolume,
        shFlow,
        szTrend,
        szVolume,
        szFlow,
        cyTrend,
        cyVolume,
        cyFlow,
        systemicRisk
      },
      sectorAnalysis: {
        reviewedEtfCount,
        hotSectors,
        etfFlowNotes
      },
      stockAnalysis: {
        top200Reviewed,
        volRatioReviewed,
        limitUpReviewed,
        diagnosedHoldings
      },
      actionAudit: {
        sellCompliant,
        profitExperience,
        lossAnalysis
      }
    };

    try {
      const res = await fetch("/api/reports/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newReport)
      });
      if (res.ok) {
        logAction(`📝 [${reviewType === "daily" ? "日报" : reviewType === "weekly" ? "周报" : "月报"}] 归档成功！日期: ${reportDate}`);
        setReportSummary("");
        setReportPlan("");
        loadAllData();
      }
    } catch (err) {
      logAction("❌ 报告归档失败");
    }
  };

  // 手动修改初始资金
  const handleResetCash = async () => {
    const cashStr = prompt(`请输入您想设定的${currentMode === "real" ? "实盘" : "模拟"}账户初始总现金 (元):`, String(accountState.initialCash));
    if (!cashStr) return;
    const cashNum = Number(cashStr);
    if (isNaN(cashNum) || cashNum <= 0) {
      alert("请输入有效的正数");
      return;
    }
    try {
      const res = await fetch("/api/account/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initialCash: cashNum })
      });
      if (res.ok) {
        logAction(`⚙️ 初始账户本金设定为: ${cashNum.toLocaleString()} 元，持仓重新审计中。`);
        loadAllData();
      }
    } catch (err) {
      logAction("❌ 设定初始资金失败");
    }
  };

  // 保存系统交易费用费率配置
  const handleSaveFees = async (newFees: typeof feeSettings) => {
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...newFees,
          currentMode
        })
      });
      if (res.ok) {
        setFeeSettings(newFees);
        logAction("⚙️ 交易手续费率已更新！后续交易录入及重算将自动同步此费率。");
        loadAllData(true);
      } else {
        alert("费用配置保存失败");
      }
    } catch (err) {
      logAction("❌ 保存费率配置通信失败");
    }
  };

  // 处理同花顺导出表格导入。导入会覆盖当前股票池，以最新表格为准。
  const handleImportFile = async () => {
    if (!importFile) {
      alert("请先选择同花顺导出的表格文件");
      return;
    }
    try {
      setLoading(true);
      logAction(`⏳ 正在导入同花顺表格并覆盖当前股票池: ${importFile.name}`);
      const params = new URLSearchParams({
        filename: importFile.name,
        fetchHistory: String(autoFetchHistoryAfterImport)
      });
      const res = await fetch(`/api/watchlist/import-file?${params.toString()}`, {
        method: "POST",
        headers: {
          "Content-Type": importFile.type || "application/octet-stream",
          "X-Filename": encodeURIComponent(importFile.name)
        },
        body: importFile
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "导入失败");
      }
      const data = await res.json();
      setWatchlist(data.list || []);
      logAction(`📂 ${data.message || "同花顺表格导入完成"}；原始代码 ${data.summary?.codeRows ?? "-"} 行，主板有效 ${data.summary?.mainBoardRows ?? "-"} 行。`);
      if (data.history) {
        logAction(`📈 自动补K线完成：成功 ${data.history.fetched || 0} 只，失败 ${data.history.failed || 0} 只。`);
      } else {
        logAction("💡 已用同花顺代码覆盖股票池，可点击「一键补充所有K线」补齐历史数据。");
      }
      setShowImportPanel(false);
      setImportFile(null);
      setWatchlistGroup("初筛");
      loadAllData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "同花顺表格导入失败");
    } finally {
      setLoading(false);
    }
  };

  // 计算交易各种费用 (用于买卖确认框实时计算)
  const calculateEstimateFees = () => {
    const amt = tradePrice * tradeQuantity;
    // 佣金: 万三，最低五元
    const comm = Math.max(5, Number((amt * 0.0003).toFixed(2)));
    // 过户费: 万零点二
    const trans = Number((amt * 0.00002).toFixed(2));
    // 印花税: 千分之零点五 (仅卖出)
    const stamp = tradeType === "SELL" ? Number((amt * 0.0005).toFixed(2)) : 0;
    const total = Number((comm + trans + stamp).toFixed(2));
    const settle = tradeType === "BUY" ? amt + total : amt - total;
    return { comm, trans, stamp, total, settle };
  };

  const est = calculateEstimateFees();

  // 判断 A股交易时间段 (9:30-11:30, 13:00-15:00)
  const isAStockTradingTime = () => {
    const h = currentTime.getHours();
    const m = currentTime.getMinutes();
    const tot = h * 60 + m;
    const isWd = currentTime.getDay() >= 1 && currentTime.getDay() <= 5;
    const morning = tot >= 9 * 60 + 30 && tot <= 11 * 60 + 30;
    const afternoon = tot >= 13 * 60 && tot <= 15 * 60;
    return isWd && (morning || afternoon);
  };

  // 股市状态与交易纪律联动说明
  const getMarketLinkedInstructions = () => {
    const h = currentTime.getHours();
    const m = currentTime.getMinutes();
    const tot = h * 60 + m;
    const isWd = currentTime.getDay() >= 1 && currentTime.getDay() <= 5;
    
    if (!isWd) {
      return {
        phase: "A股已收盘 (周末/休市期)",
        bg: "bg-slate-900/60 border-slate-800 text-slate-300",
        action: "收盘写快照与周复盘",
        color: "text-slate-400",
        guidelines: [
          "💡 自我审计：进入「交易记录审计」和「复盘笔记归档」，总结本周的所有交易操作是否严格执行买入偏离度（0%~2%）和卖出（跌破MA5）纪律。",
          "💡 模拟训练备战：切换到「模拟训练」模式，点击「清空交易流水」并重新设定模拟本金进行超短线操盘练习，巩固对回踩均线低吸的认知。"
        ]
      };
    }
    
    if (tot < 9 * 60 + 30) {
      return {
        phase: "A股开盘前 (盘前备战 08:30 - 09:30)",
        bg: "bg-blue-950/30 border-blue-900/60 text-blue-200",
        action: "盘前重计算",
        color: "text-blue-400",
        guidelines: [
          "🎯 构建初筛池：点击「生成今日初筛池」一键拉取主板成交额最强的前30标的（系统已智能排除ST、创业板、科创板、北交及笨重股）。",
          "🎯 均线指标补齐：在「股票池」界面，点击「一键补充全量K线」加载历史均线指标。评估哪些强势股有回踩均线潜能，加入 [观察] 分组。",
          "⚠️ 戒骄戒躁：开盘前严禁凭临时直觉/意念追涨下单挂单！必须静待盘中严格的回踩买点出现。"
        ]
      };
    } else if (tot >= 9 * 60 + 30 && tot < 9 * 60 + 35) {
      return {
        phase: "A股开盘过渡期 (09:30 - 09:35)",
        bg: "bg-amber-950/40 border-amber-900/60 text-amber-200",
        action: "开盘静默观察",
        color: "text-amber-400",
        guidelines: [
          "⚠️ 严防乱买冲动：开盘前5分钟（09:30 - 09:35）盘面变化极度剧烈，高开低走与诱多频繁，不建议在此期间做任何买入操作！",
          "⚡ 监控持仓次日强度：如果今天有可卖持仓，需观察高开或低开状态。如果10点前股价无力上攻或冲高回落，考虑做好冲高离场准备。"
        ]
      };
    } else if (tot >= 9 * 60 + 35 && tot <= 10 * 60) {
      return {
        phase: "早盘低吸黄金窗口 (09:35 - 10:00)",
        bg: "bg-emerald-950/30 border-emerald-900/60 text-emerald-200",
        action: "均线低吸介入",
        color: "text-emerald-400",
        guidelines: [
          "✅ 符合铁律买入期：此时间段主力拉升或踩支撑意图已初步明晰。立即核对「等回踩」和「待买」列表！",
          "📈 黄金偏离率买入：若看好个股出现回踩5日线，偏离度在 0% ~ 2% 且未有效跌破MA5，符合低吸纪律，可轻仓/按批次记录买入。"
        ]
      };
    } else if (tot > 10 * 60 && tot < 13 * 60) {
      return {
        phase: "盘中静默观察期 (10:00 - 13:00)",
        bg: "bg-slate-950/40 border-slate-800 text-slate-300",
        action: "坚决克制不买",
        color: "text-slate-400",
        guidelines: [
          "❌ 严禁盘中追涨：10:00 到 11:30（以及午休）是主力拉高出货或无量诱多的震荡多发期，此时段追大阳线极易吃套！",
          "⚠️ 纪律约束：只看盘、不交易，不根据短时间内的秒级拉升草率挂单。等待下午尾盘定乾坤的机会。"
        ]
      };
    } else if (tot >= 13 * 60 && tot < 14 * 60 + 30) {
      return {
        phase: "午盘观察静默期 (13:00 - 14:30)",
        bg: "bg-slate-950/40 border-slate-800 text-slate-300",
        action: "耐心看盘不买",
        color: "text-slate-400",
        guidelines: [
          "❌ 严禁午后追涨：午后开盘往往成交量低迷，个股波动缺乏持续性。此时买入，次日极易陷入被动。",
          "🔍 备战尾盘：密切锁定加入自选的「等回踩」个股。看是否有标的在 14:30 后稳步回落至 5 日线附近、而不形成破位。"
        ]
      };
    } else if (tot >= 14 * 60 + 30 && tot < 14 * 60 + 50) {
      return {
        phase: "尾盘低吸确认窗口 (14:30 - 14:50)",
        bg: "bg-emerald-950/30 border-emerald-900/60 text-emerald-200",
        action: "尾盘支撑低吸",
        color: "text-emerald-400",
        guidelines: [
          "✅ 尾盘安全买入期：由于收盘临近，5日线支撑是否有效已得到基本确认，是判定大阳股回踩低吸最为安全的防诱多买点时点！",
          "📈 支撑校验：若股价平稳落在5日线附近，偏离度在 0% ~ 2% 且5日线未跌破，可分批补录建仓，锁定低吸机会。"
        ]
      };
    } else if (tot >= 14 * 60 + 50 && tot <= 14 * 60 + 55) {
      return {
        phase: "尾盘持仓风控执行时段 (14:50 - 14:55)",
        bg: "bg-rose-950/40 border-rose-900 text-rose-200 animate-pulse",
        action: "强制风控对账",
        color: "text-rose-400",
        guidelines: [
          "🚨 【风控铁律】14:50 持仓对账与风控时间！请立刻检查您的「持仓监控」！",
          "💀 跌破 MA5 必卖：若持仓股当前价格仍处于 5日均线（MA5）下方（即偏离度 < 0%），已触发强制止损减仓机制。必须在 14:55 前果断记录卖出、锁死亏损！防止次日加速下跌！"
        ]
      };
    } else if (tot > 14 * 60 + 55 && tot < 15 * 60) {
      return {
        phase: "尾盘锁定静默期 (14:55 - 15:00)",
        bg: "bg-amber-950/40 border-amber-900/60 text-amber-200",
        action: "锁定交易静默",
        color: "text-amber-400",
        guidelines: [
          "⚠️ 严禁最后几分钟胡乱下单：14:57 以后进入集合竞价锁死。拒绝任何赌博性质的草率决定！",
          "📝 盘后对账备战：收拾心情，准备迎接收盘后的账目盈亏核算与复盘总结。"
        ]
      };
    } else {
      return {
        phase: "A股已收盘",
        bg: "bg-slate-900 border-slate-800 text-slate-300",
        action: "收盘复盘总结",
        color: "text-slate-400",
        guidelines: [
          "📝 流水补录对账：仔细核对今日的所有交易记录是否完备。系统已根据昨日K线与偏离度对您今日的所有买卖自动完成合规审计。",
          "📝 复盘日记归档：进入「复盘笔记归档」工作台，书写今日心得并生成复盘日报，客观审视今日是否存在违规交易。"
        ]
      };
    }
  };

  // 今日复盘相关计算
  const todayStrForReview = new Date().toISOString().split("T")[0];
  const todayTrades = trades.filter(t => t.date === todayStrForReview);
  const reviewBuyCount = todayTrades.filter(t => t.type === "BUY").length;
  const reviewCompliantCount = todayTrades.filter(t => t.type === "BUY" && t.rulesConclusion === "符合规则").length;
  const complianceRate = reviewBuyCount > 0 ? Number(((reviewCompliantCount / reviewBuyCount) * 100).toFixed(2)) : 100;

  const hasStrongStartSignal = (stock: Stock) => stock.bigCandlePct >= 5;
  const hasValidMa5 = (stock: Stock) => stock.ma5 > 0;
  const observationStages: StockStage[] = ["接近买点", "等回踩", "远离不追"];
  const observationStageForStock = (stock: Stock): StockStage | null => {
    if (hasStrongStartSignal(stock) && hasValidMa5(stock) && stock.ma5Upward && stock.deviation5 >= 0) {
      if (stock.deviation5 <= 2) return "接近买点";
      if (stock.deviation5 <= 7) return "等回踩";
      return "远离不追";
    }
    return observationStages.includes(stock.stage) ? stock.stage : null;
  };
  const isObservationStock = (stock: Stock) => observationStageForStock(stock) !== null;

  const stockBelongsToGroup = (stock: Stock, group: StockGroup) => {
    if (group === "初筛") return true;
    if (group === "持仓") {
      return positions.some(pos => pos.code === stock.code) || stock.group === "持仓";
    }
    if (group === "待买") {
      return Boolean(stock.canBuy);
    }
    if (group === "观察") return isObservationStock(stock);
    return false;
  };

  const stocksForGroup = (list: Stock[], group: StockGroup) => (
    list.filter(stock => stockBelongsToGroup(stock, group))
  );

  const firstStockForGroup = (list: Stock[], group: StockGroup) => (
    stocksForGroup(list, group)[0] || list[0]
  );

  const buyReadyStocks = stocksForGroup(watchlist, "待买");

  // 股票搜索过滤。初筛是成交额前30基础池；观察/待买是从基础池派生出的规则视图。
  const filteredWatchlist = watchlist.filter(s => {
    if (!stockBelongsToGroup(s, watchlistGroup)) return false;
    if (searchQuery) {
      return s.code.includes(searchQuery) || s.name.includes(searchQuery);
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col font-sans selection:bg-blue-500/20 selection:text-blue-200">
      
      {/* 顶部系统状态 Bar */}
      <header className="bg-slate-900 border-b border-slate-800 py-3 px-4 flex flex-wrap items-center justify-between sticky top-0 z-40 shadow-sm text-white gap-3">
        <div className="flex items-center space-x-3">
          <div className="bg-gradient-to-tr from-blue-600 to-indigo-500 p-1.5 rounded-lg shadow-inner">
            <ShieldAlert className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white">强势回踩短线交易纪律系统</h1>
            <p className="text-[10px] text-slate-400">主板前排股票 5日线低吸回踩纪律工作台</p>
          </div>
        </div>

        {/* 模式切换器 */}
        <div className="flex items-center space-x-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => handleToggleMode("simulation")}
            className={`px-3 py-1 rounded text-xs font-semibold transition-all ${
              currentMode === "simulation"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            模拟训练
          </button>
          <button
            onClick={() => handleToggleMode("real")}
            className={`px-3 py-1 rounded text-xs font-semibold transition-all ${
              currentMode === "real"
                ? "bg-rose-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            实盘记录
          </button>
        </div>

        {/* 同花顺风格账户资产栏 */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs font-mono py-1.5 px-4 bg-slate-950/70 border border-slate-800 rounded-lg">
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[10px]">{currentMode === "real" ? "实盘总资产:" : "模拟总资产:"}</span>
            <span className="font-bold text-slate-100 text-[12px]">{accountState.totalAssets.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[10px]">总市值:</span>
            <span className="font-bold text-amber-500 text-[12px]">{accountState.holdingValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[10px]">可用资金:</span>
            <span className="font-bold text-slate-100 text-[12px]">{accountState.availableCash.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[10px]">总盈亏:</span>
            <span className={`font-bold text-[12px] ${accountState.totalPnL >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
              {accountState.totalPnL >= 0 ? "+" : ""}{accountState.totalPnL.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[10px]">当日盈亏:</span>
            <span className={`font-bold text-[12px] ${accountState.todayPnL !== undefined && accountState.todayPnL >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
              {accountState.todayPnL !== undefined && accountState.todayPnL >= 0 ? "+" : ""}{accountState.todayPnL !== undefined ? accountState.todayPnL.toLocaleString(undefined, { minimumFractionDigits: 2 }) : "0.00"}
            </span>
          </div>
          <div className="flex items-center space-x-1.5 last:border-0">
            <span className="text-slate-400 text-[10px]">总收益率:</span>
            <span className={`font-bold text-[12px] ${accountState.totalPnL >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
              {accountState.totalPnL >= 0 ? "+" : ""}{accountState.totalReturnPct.toFixed(2)}%
            </span>
          </div>
        </div>

        {/* A股开盘时间时钟 */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          <div className="text-right">
            <div className="text-slate-100 font-medium">{currentTime.toLocaleTimeString()}</div>
            <div className="flex items-center space-x-1 justify-end mt-0.5">
              <span className={`h-2 w-2 rounded-full ${isAStockTradingTime() ? "bg-rose-500 animate-pulse" : "bg-slate-700"}`}></span>
              <span className="text-[10px] text-slate-400">{isAStockTradingTime() ? "A股交易时间中" : "A股已休市"}</span>
            </div>
          </div>
        </div>
      </header>

      {/* 核心工作区分割 */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        
        {/* 左侧菜单导航 */}
        <nav className="w-full md:w-56 bg-slate-900 border-b md:border-b-0 md:border-r border-slate-800 p-3 flex flex-row md:flex-col justify-around md:justify-start space-y-0 md:space-y-1.5 shrink-0 overflow-x-auto">
          <div className="hidden md:block px-3 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">纪律罗盘</div>
          
          <button
            onClick={() => setActiveTab("dashboard")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "dashboard" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <Activity className="h-4 w-4" />
            <span>今日看板</span>
          </button>

          <button
            onClick={() => setActiveTab("watchlist")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "watchlist" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <Briefcase className="h-4 w-4" />
            <span>股票池 & 分组</span>
          </button>

          <button
            onClick={() => setActiveTab("intraday")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "intraday" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <TrendingUp className="h-4 w-4" />
            <span>盘中低吸监控</span>
          </button>

                    <button
            onClick={() => setActiveTab("trades")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "trades" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <History className="h-4 w-4" />
            <span>交易记录审计</span>
          </button>

          <button
            onClick={() => setActiveTab("review")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "review" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <FileText className="h-4 w-4" />
            <span>复盘笔记归档</span>
          </button>

          <button
            onClick={() => setActiveTab("settings")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "settings" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <Settings className="h-4 w-4" />
            <span>交易系统配置</span>
          </button>

          {/* 实时运行操作日志 */}
          <div className="hidden md:flex flex-col flex-1 mt-6 border-t border-slate-800/60 pt-4 overflow-hidden">
            <span className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">事件流日志</span>
            <div className="flex-1 bg-slate-950 border border-slate-850 rounded-lg p-2 font-mono text-[9px] text-slate-400 overflow-y-auto space-y-1.5 max-h-[350px] min-h-[220px]">
              {actionLog.length === 0 ? (
                <div className="text-center py-4 italic">暂无系统事件</div>
              ) : (
                actionLog.map((log, i) => (
                  <div key={i} className="leading-relaxed border-b border-slate-900 pb-1 last:border-0">{log}</div>
                ))
              )}
            </div>
          </div>
        </nav>

        {/* 右侧主视口 */}
        <main className="flex-1 bg-slate-950 p-4 md:p-6 overflow-y-auto">
          {loading && (
            <div className="fixed top-12 right-6 bg-blue-600 border border-blue-500 text-white text-[10px] font-mono py-1 px-3.5 rounded shadow-lg flex items-center space-x-2 animate-bounce z-50">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-white animate-ping"></span>
              <span>同步中...</span>
            </div>
          )}

          {/* TAB 1: 今日看板 */}
          {activeTab === "dashboard" && (
            <div className="space-y-6">
              
              {/* 热力引导语 */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between shadow-sm space-y-3 md:space-y-0">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="h-4 w-4 text-amber-400 fill-amber-400" />
                    <h3 className="text-sm font-semibold text-slate-200">欢迎使用强势回踩短线交易纪律系统</h3>
                  </div>
                  <p className="text-xs text-slate-400">本系统围绕<b>沪深主板前排股5日均线（0%~2%）回踩低吸</b>交易纪律，约束盘前选股，强化交易存证，阻断乱买冲动。</p>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleGenerateStockPool}
                    className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold shadow-sm flex items-center space-x-1.5 transition"
                  >
                    <Briefcase className="h-3.5 w-3.5" />
                    <span>生成今日初筛池</span>
                  </button>
                  <button
                    onClick={handleRefreshQuotes}
                    className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded text-xs font-semibold shadow-sm flex items-center space-x-1.5 transition"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    <span>盘中轻量刷新</span>
                  </button>
                </div>
              </div>

              {/* 🚦 股市状态联动交易纪律指南 */}
              {(() => {
                const instr = getMarketLinkedInstructions();
                return (
                  <div className={`border p-4 rounded-xl shadow-sm ${instr.bg} space-y-3`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="flex h-2.5 w-2.5 relative">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
                        </span>
                        <h4 className="text-xs font-bold uppercase tracking-wider">
                          🚦 {instr.phase}
                        </h4>
                      </div>
                      <span className="text-[10px] bg-slate-950/10 px-2.5 py-0.5 rounded-full font-bold">
                        {instr.action}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      <h5 className="text-xs font-bold">按照纪律规则，当前您应当执行以下操作：</h5>
                      <div className="text-xs space-y-1 pl-1 leading-relaxed">
                        {instr.guidelines.map((g, idx) => (
                          <p key={idx} className="font-medium">{g}</p>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* 大统计面板 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-400 font-bold uppercase block tracking-wider">主板初筛</span>
                  <div className="flex items-baseline space-x-2 mt-1">
                    <span className="text-2xl font-bold text-slate-100">{stocksForGroup(watchlist, "初筛").length}</span>
                    <span className="text-[10px] text-slate-400 font-medium">基础候选</span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-2">成交额前30，已排除ST/创业/科创/北交等</p>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-400 font-bold uppercase block tracking-wider">观察</span>
                  <div className="flex items-baseline space-x-2 mt-1">
                    <span className="text-2xl font-bold text-slate-100">{stocksForGroup(watchlist, "观察").length}</span>
                    <span className="text-[10px] text-slate-400 font-medium">等待回踩</span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-2">只含接近买点、等回踩、远离不追</p>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm border-l-cyan-500 border-l-4">
                  <span className="text-[10px] text-cyan-400 font-bold uppercase block tracking-wider">待买观察</span>
                  <div className="flex items-baseline space-x-2 mt-1">
                    <span className="text-2xl font-bold text-cyan-400">{buyReadyStocks.length}</span>
                    <span className="text-[10px] text-cyan-500 font-medium">重点盯</span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-2">大阳启动后回踩MA5 0%~2%，未跌破</p>
                </div>
              </div>

              {/* 今日账户资产与资金动态监控 (同花顺风格) */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                  <div className="flex items-center space-x-2">
                    <TrendingUp className="h-4 w-4 text-cyan-400" />
                    <h3 className="text-xs font-extrabold text-slate-200 uppercase tracking-wider">
                      今日持仓资产与资金动态监控
                    </h3>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-[10px] text-slate-400">初始总本金:</span>
                    <span className="text-xs font-mono font-bold text-slate-200">
                      ¥{accountState.initialCash.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                    <button
                      onClick={handleResetCash}
                      className="text-[10px] text-cyan-400 hover:text-cyan-300 border border-cyan-500/20 px-2 py-0.5 rounded bg-cyan-950/40 hover:bg-cyan-950/70 ml-2 transition"
                    >
                      修改本金
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-850/60">
                    <span className="text-[10px] text-slate-400 block mb-1">今日账户总资产</span>
                    <span className="text-sm font-mono font-extrabold text-slate-100 block">
                      ¥{accountState.totalAssets.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-850/60">
                    <span className="text-[10px] text-slate-400 block mb-1">可用现金余额</span>
                    <span className="text-sm font-mono font-extrabold text-slate-100 block">
                      ¥{accountState.availableCash.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-850/60">
                    <span className="text-[10px] text-slate-400 block mb-1">当前持仓市值</span>
                    <span className="text-sm font-mono font-extrabold text-amber-500 block">
                      ¥{accountState.holdingValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-850/60">
                    <span className="text-[10px] text-slate-400 block mb-1">当日浮动盈亏</span>
                    <span className={`text-sm font-mono font-extrabold block ${accountState.todayPnL !== undefined && accountState.todayPnL >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
                      {accountState.todayPnL !== undefined && accountState.todayPnL >= 0 ? "+" : ""}{accountState.todayPnL !== undefined ? accountState.todayPnL.toLocaleString(undefined, { minimumFractionDigits: 2 }) : "0.00"}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-400 bg-slate-950/40 p-2.5 rounded-md border border-slate-800/40">
                  <div>
                    <span>累计实现盈亏: </span>
                    <span className={`font-mono font-bold ${accountState.totalPnL >= 0 ? "text-rose-400" : "text-emerald-400"}`}>
                      {accountState.totalPnL >= 0 ? "+" : ""}{accountState.totalPnL.toLocaleString(undefined, { minimumFractionDigits: 2 })} 元
                    </span>
                  </div>
                  <div>
                    <span>账户总收益率: </span>
                    <span className={`font-mono font-bold ${accountState.totalPnL >= 0 ? "text-rose-400" : "text-emerald-400"}`}>
                      {accountState.totalPnL >= 0 ? "+" : ""}{accountState.totalReturnPct.toFixed(2)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* 持仓风控与交易铁律操作指南卡 */}
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <ShieldAlert className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-xs font-extrabold text-slate-200 uppercase tracking-wider">
                    当前持仓风控监控与操作建议
                  </h3>
                </div>

                {positions.length === 0 ? (
                  <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 text-center text-xs text-slate-500 italic">
                    💡 当前账户暂无任何持仓。符合回踩 5 日均线的主板强势股启动后，可在「股票池」录入买入流水建仓。
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-4">
                    {positions.map(p => {
                      const isDanger = p.riskLevel === "danger";
                      const isWarning = p.riskLevel === "warning";
                      const deviation = p.deviation5;

                      let bgClass = "bg-slate-900/60 border-slate-800 text-slate-200";
                      let titleLabel = "趋势观察中";
                      let adviceText = "股价运行于 5 日线（MA5）上方且未过度发散，运行良好，请继续坚守纪律持有。";

                      if (isDanger) {
                        bgClass = "bg-rose-950/40 border-rose-900/80 text-rose-200 animate-pulse";
                        titleLabel = "破位风控警告！";
                        adviceText = `股价已跌破 5日均线（MA5: ¥${p.ma5.toFixed(2)}，偏离度: ${deviation}%）！根据超短线铁律：今日尾盘 14:50 仍无法收回，请于 14:55 前坚决减仓或卖出！若跌破后连续 3 天站不回，无条件全部清仓！`;
                      } else if (isWarning) {
                        bgClass = "bg-amber-950/40 border-amber-900/60 text-amber-200";
                        titleLabel = "远离均线止盈！";
                        adviceText = `股价偏离 5日均线过高（偏离度: ${deviation}% > 7%）！超短线获利丰厚，极易冲高回落。若持股为100股：要么持有、要么全卖；若持股在200股以上：可先考虑获利减仓一半止盈，落袋为安。`;
                      } else if (deviation >= 0 && deviation <= 2.0) {
                        bgClass = "bg-emerald-950/30 border-emerald-900/60 text-emerald-200";
                        titleLabel = "均线低吸金区";
                        adviceText = `当前正好运行于 5日线金区上方贴边运行（偏离度: ${deviation}%）。均线支撑保持向上，是最具盈亏比的健康持仓状态，请暂维持不动。`;
                      }

                      return (
                        <div key={p.code} className={`border rounded-xl p-4 space-y-3 ${bgClass}`}>
                          <div className="flex items-center justify-between border-b border-slate-800/40 pb-2">
                            <div className="flex items-center space-x-2">
                              <span className={`h-2.5 w-2.5 rounded-full ${isDanger ? "bg-rose-500" : isWarning ? "bg-amber-500" : "bg-emerald-500"}`}></span>
                              <span className="font-mono text-xs font-bold text-slate-200">
                                {p.name} ({p.code})
                              </span>
                            </div>
                            <span className="text-[10px] font-extrabold uppercase tracking-widest px-2.5 py-0.5 rounded bg-slate-950/40 text-slate-200">
                              {titleLabel}
                            </span>
                          </div>

                          <div className="grid grid-cols-3 gap-2 text-center text-[10px] font-mono py-1.5 bg-slate-950/30 rounded border border-slate-850/40">
                            <div>
                              <span className="text-slate-400 block text-[9px] mb-0.5">当前持股</span>
                              <span className="font-bold text-slate-200">{p.quantity} 股</span>
                            </div>
                            <div>
                              <span className="text-slate-400 block text-[9px] mb-0.5">持仓均价</span>
                              <span className="font-bold text-slate-200">¥{p.avgCost.toFixed(2)}</span>
                            </div>
                            <div>
                              <span className="text-slate-400 block text-[9px] mb-0.5">当前现价</span>
                              <span className="font-bold text-slate-100 font-extrabold">¥{p.currentPrice.toFixed(2)}</span>
                            </div>
                          </div>

                          <div className="flex items-center justify-between text-[11px] font-mono">
                            <span className="text-slate-400">5 日均线: <b className="text-slate-200">¥{p.ma5.toFixed(2)}</b></span>
                            <span className="text-slate-400">5日偏离率: <b className={deviation < 0 ? "text-emerald-400" : "text-rose-400"}>{deviation}%</b></span>
                          </div>

                          <div className="text-xs leading-relaxed border-t border-slate-800/40 pt-2 text-slate-300">
                            <span className="font-extrabold text-slate-100 block mb-0.5">防守/风控策略:</span>
                            {adviceText}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* ACTIVE PLAYBOOK | 强势回踩交易铁律控制台 */}
              <div className="space-y-4">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
                  <div className="border-b border-slate-800 pb-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="space-y-1">
                      <span className="text-[10px] text-cyan-400 font-extrabold uppercase tracking-widest block">ACTIVE PLAYBOOK</span>
                      <h3 className="text-sm font-black text-slate-100 flex items-center space-x-2">
                        <span>主板成交额前排强势股的 5 日线回踩低吸模式</span>
                      </h3>
                    </div>
                    <p className="text-[11px] text-slate-400 font-medium">只在强势确认后等待 MA5 附近回踩；进入待买也必须经过资金、时间和风控校验。</p>
                  </div>

                  {/* 6格铁律矩阵 */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {/* 1. 股票范围 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <Briefcase className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">股票范围</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">沪深主板 A 股</h4>
                        <p className="text-[11px] text-slate-400 leading-normal">
                          代码以 600/601/603/605/000/001/002 开头。<b>排除 ST、创业板、科创板、北交所及京东方A等笨重股</b>，坚决只做主板前排最强流动性大阳股！
                        </p>
                      </div>
                    </div>

                    {/* 2. 强势确认 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <TrendingUp className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">强势确认</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">近 10-20 日有 ≥5% 阳线</h4>
                        <p className="text-[11px] text-slate-400 leading-normal">
                          近 20 个交易日内必须出现过单日涨幅大于或等于 <b>5%</b>、且收盘高于开盘的阳线，证明已有强势启动信号。
                        </p>
                      </div>
                    </div>

                    {/* 3. 买点区间 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <CheckCircle2 className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">买点区间</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">距 MA5 0% ~ 2% 黄金低吸金区</h4>
                        <p className="text-[11px] text-slate-400 leading-normal">
                          股价调整回踩至 <b>0%~2%</b> 为接近买点；<b>2%~7%</b> 等回踩；<b>&gt;7%</b> 远离不追；<b>&lt;0%</b> 跌破MA5，不进入观察池。
                        </p>
                      </div>
                    </div>

                    {/* 4. 买入时间 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <Calendar className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">买入时间</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">9:35-10:00 / 14:30-14:55</h4>
                        <p className="text-[11px] text-slate-400 leading-normal">
                          早盘 9:35 确认高位承接且不破 MA5 收回；尾盘 14:30-14:55 确认支撑彻底稳固。<b>严禁 9:30 抢开盘、午盘中段或临期最后几分钟无计划追高。</b>
                        </p>
                      </div>
                    </div>

                    {/* 5. 资金约束 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <Coins className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">资金约束</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">可用资金: ¥{accountState.availableCash.toLocaleString(undefined, { minimumFractionDigits: 2 })}</h4>
                        <p className="text-[11px] text-slate-400 leading-normal">
                          单只标的最少买 1 手（100股）。现金不足 1 手时坚决克制手痒不买，任何时候<b>绝不私用未授权高杠杆</b>，记录交易时严格检验账面现金。
                        </p>
                      </div>
                    </div>

                    {/* 6. 卖出纪律 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <AlertCircle className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">卖出纪律</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">5 日线管理仓位 (若大盘风险收紧止损位)</h4>
                        <p className="text-[11px] text-slate-400 leading-normal">
                          次日 10:00 前不强就走（无溢价冲高无力）；远离 MA5 止盈；14:50 跌破看减仓/直接清仓；3日不收回强制淘汰。<b>若大盘见顶或大阴系统性风险，单股止损位由 9~10% 严格上调收紧到 7~8% 铁律！</b>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 纪律流水快捷补录控制台 */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-4 shadow-md">
                  <div className="space-y-1">
                    <h4 className="text-xs font-bold uppercase text-slate-200 tracking-wider flex items-center space-x-1.5">
                      <Plus className="h-3.5 w-3.5 text-cyan-400" />
                      <span>短线实盘交易补录控制台</span>
                    </h4>
                    <p className="text-[10px] text-slate-400 leading-normal">在实盘/模拟盘中成交后，请在此记入，系统自动同步审计，并在「交易记录审计」生成违规证据归档。</p>
                  </div>
                  <div className="flex items-center space-x-3 w-full md:w-auto shrink-0">
                    <button
                      onClick={() => {
                        setActiveTab("watchlist");
                        setWatchlistGroup("待买");
                        logAction("💡 请在待买列表中选中股票，并在右侧详情卡进行盘中手动确认");
                      }}
                      className="flex-1 md:flex-initial px-5 py-2.5 bg-rose-950/50 hover:bg-rose-900/50 border border-rose-900/60 rounded-lg font-bold text-xs text-rose-300 transition duration-150 text-center active:scale-95 cursor-pointer"
                    >
                      💡 记录实盘买入
                    </button>
                    <button
                      onClick={() => {
                        setActiveTab("watchlist");
                        setWatchlistGroup("持仓");
                        logAction("💡 请在持仓列表中选中对应股，点击「确认卖出」归档");
                      }}
                      className="flex-1 md:flex-initial px-5 py-2.5 bg-emerald-950/50 hover:bg-emerald-900/50 border border-emerald-900/60 rounded-lg font-bold text-xs text-emerald-300 transition duration-150 text-center active:scale-95 cursor-pointer"
                    >
                      💡 记录实盘卖出
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: 股票池与分组表格 */}
          {activeTab === "watchlist" && (
            <div className="space-y-4">
              
              {/* 同花顺导入/股票池操作行 */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-3 rounded-lg">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={handleGenerateStockPool}
                    className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold transition"
                  >
                    自动筛选并覆盖前30
                  </button>
                  <button
                    onClick={() => handleFetchHistory(undefined, true)}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded text-xs font-semibold transition"
                  >
                    一键补充所有K线
                  </button>
                  <button
                    onClick={() => setShowImportPanel(!showImportPanel)}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded text-xs font-semibold flex items-center space-x-1.5 transition"
                  >
                    <FileSpreadsheet className="h-3.5 w-3.5" />
                    <span>上传同花顺覆盖</span>
                  </button>
                </div>

                <div className="relative">
                  <Search className="h-3.5 w-3.5 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="输入代码或名称搜索..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full sm:w-60 pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs focus:outline-none focus:border-cyan-500 font-mono text-slate-200"
                  />
                </div>
              </div>

              {/* 同花顺表格导入区域 */}
              {showImportPanel && (
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                    <span className="text-xs font-bold text-slate-300">同花顺表格导入当前初筛池</span>
                    <button onClick={() => setShowImportPanel(false)} className="text-slate-500 hover:text-slate-300 text-xs">取消</button>
                  </div>
                  <p className="text-[10px] text-slate-500">
                    支持 .xlsx / .xls / .csv。系统会以表格中的股票代码为准，清洗成沪深主板前30只并覆盖当前股票池；旧股票池会先自动备份。
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-center">
                    <input
                      type="file"
                      accept=".xlsx,.xls,.csv"
                      onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-300 hover:file:bg-slate-700"
                    />
                    <label className="flex items-center gap-2 text-[11px] text-slate-400">
                      <input
                        type="checkbox"
                        checked={autoFetchHistoryAfterImport}
                        onChange={(e) => setAutoFetchHistoryAfterImport(e.target.checked)}
                        className="h-3.5 w-3.5 accent-cyan-500"
                      />
                      导入后自动补K线
                    </label>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[10px] text-slate-500">
                      {importFile ? `已选择: ${importFile.name}` : "尚未选择文件"}
                    </span>
                    <button
                      onClick={handleImportFile}
                      disabled={!importFile || loading}
                      className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded text-xs font-semibold"
                    >
                      覆盖导入
                    </button>
                  </div>
                </div>
              )}

              {/* 分组 TAB 与表格视口 */}
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
                
                {/* 列表区域 */}
                <div className="xl:col-span-2 space-y-3">
                  
                  {/* 分组 Tab 切换器 */}
                  <div className="flex bg-slate-900 border border-slate-800 p-1 rounded-lg">
                    {(["初筛", "观察", "待买"] as StockGroup[]).map(gp => {
                      const count = stocksForGroup(watchlist, gp).length;
                      return (
                        <button
                          key={gp}
                          onClick={() => {
                            setWatchlistGroup(gp);
                            // 默认选择当前派生视图中的第一个
                            const first = firstStockForGroup(watchlist, gp);
                            if (first) setSelectedStock(first);
                          }}
                          className={`flex-1 py-1.5 text-xs font-bold rounded-md transition ${watchlistGroup === gp ? "bg-slate-950 text-cyan-400 shadow-inner" : "text-slate-500 hover:text-slate-300"}`}
                        >
                          {gp} ({count})
                        </button>
                      );
                    })}
                  </div>

                  {/* 表格 */}
                  <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-slate-800/80 bg-slate-950/40 text-slate-500 font-mono">
                          <th className="p-3">股票</th>
                          <th className="p-3 text-right">最新现价</th>
                          <th className="p-3 text-right">涨跌幅</th>
                          <th className="p-3 text-right">成交额(万)</th>
                          <th className="p-3 text-right">5日偏离率</th>
                          <th className="p-3 text-right">大阳特征</th>
                          <th className="p-3">流程阶段 / 状态</th>
                          <th className="p-3">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredWatchlist.length === 0 ? (
                          <tr>
                            <td colSpan={8} className="p-8 text-center text-slate-500 italic">
                              当前分组暂无匹配的股票
                            </td>
                          </tr>
                        ) : (
                          filteredWatchlist.map(s => {
                            const isSelected = selectedStock?.code === s.code;
                            const displayStage = watchlistGroup === "待买"
                              ? "待买观察"
                              : watchlistGroup === "观察"
                                ? (observationStageForStock(s) || s.stage)
                                : s.stage;
                            return (
                              <tr
                                key={s.code}
                                onClick={() => setSelectedStock(s)}
                                className={`border-b border-slate-800/40 hover:bg-slate-800/30 cursor-pointer transition ${isSelected ? "bg-slate-800/50" : ""}`}
                              >
                                <td className="p-3 font-mono">
                                  <div className="font-semibold text-slate-200">{s.name}</div>
                                  <div className="text-[10px] text-slate-500">{s.code}</div>
                                </td>
                                <td className="p-3 text-right font-mono font-semibold text-slate-300">
                                  {s.price > 0 ? s.price.toFixed(2) : "未同步"}
                                </td>
                                <td className={`p-3 text-right font-mono font-semibold ${s.pct >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
                                  {s.pct >= 0 ? "+" : ""}{s.pct.toFixed(2)}%
                                </td>
                                <td className="p-3 text-right font-mono text-slate-400">
                                  {s.volume > 0 ? (s.volume / 10000).toLocaleString(undefined, { maximumFractionDigits: 0 }) : "0"}
                                </td>
                                <td className={`p-3 text-right font-mono font-bold ${s.deviation5 < 0 ? "text-emerald-500" : s.deviation5 <= 2.0 ? "text-cyan-400 underline decoration-cyan-500" : "text-rose-400"}`}>
                                  {s.deviation5}%
                                </td>
                                <td className="p-3 text-right font-mono text-slate-400">
                                  {s.bigCandlePct > 0 ? `${s.bigCandlePct}%` : "未计算"}
                                </td>
                                <td className="p-3">
                                  <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                                    displayStage === "待买观察" || displayStage === "接近买点" ? "bg-cyan-950 text-cyan-400 border border-cyan-500/20" :
                                    displayStage === "等回踩" ? "bg-amber-950 text-amber-400 border border-amber-500/20" :
                                    displayStage === "远离不追" ? "bg-rose-950 text-rose-400 border border-rose-500/20" :
                                    "bg-slate-800 text-slate-400"
                                  }`}>
                                    {displayStage}
                                  </span>
                                </td>
                                <td className="p-3" onClick={e => e.stopPropagation()}>
                                  <div className="flex space-x-1.5">
                                    {s.historyStatus !== "已有缓存" && (
                                      <button
                                        onClick={() => handleFetchHistory(s.code)}
                                        className="px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-cyan-400 text-[10px] rounded"
                                        title="补充单只历史均线"
                                      >
                                        补K线
                                      </button>
                                    )}
                                    {watchlistGroup === "待买" && (
                                      <button
                                        onClick={() => openBuyModal(s)}
                                        className="px-2 py-0.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold text-[10px] rounded"
                                      >
                                        盘中确认
                                      </button>
                                    )}
                                    {watchlistGroup === "持仓" && (
                                      <button
                                        onClick={() => {
                                          const pos = positions.find(p => p.code === s.code);
                                          if (pos) openSellModal(pos);
                                        }}
                                        className="px-2 py-0.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-[10px] rounded"
                                      >
                                        确认卖出
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 右侧详情及 K 线分析区域 */}
                <div className="space-y-4">
                  {selectedStock ? (
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4 shadow-md">
                      
                      {/* 标题 */}
                      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                        <div>
                          <h3 className="text-sm font-bold text-slate-200">{selectedStock.name}</h3>
                          <span className="text-[10px] text-slate-500 font-mono">{selectedStock.code} | {isMainBoard(selectedStock.code) ? "主板" : "非主板"}</span>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${selectedStock.ma5Upward ? "bg-rose-950 text-rose-400 border border-rose-500/20" : "bg-slate-950 text-slate-500"}`}>
                          {selectedStock.ma5Upward ? "MA5 向上 ↗" : "MA5参考"}
                        </span>
                      </div>

                      {/* 实盘 K 线渲染 */}
                      <KLineChart code={selectedStock.code} name={selectedStock.name} />

                      {/* 规则诊断分析 */}
                      <div className="bg-slate-950/80 border border-slate-850 p-3 rounded-lg space-y-2">
                        <div className="text-xs font-semibold text-slate-300 flex items-center space-x-1">
                          <Info className="h-3.5 w-3.5 text-cyan-400" />
                          <span>纪律诊断结论：</span>
                        </div>
                        <p className="text-xs text-slate-400 font-mono leading-relaxed">{selectedStock.reason || "暂未计算得出诊断。您可以点击一键刷新重新诊断。"}</p>
                        
                        {selectedStock.reminder && (
                          <div className="border-t border-slate-800/40 pt-1.5 mt-1.5 flex items-start space-x-1.5">
                            <span className="text-[10px] font-bold text-cyan-500 uppercase shrink-0 mt-0.5">指令:</span>
                            <span className="text-xs text-slate-300 font-medium">{selectedStock.reminder}</span>
                          </div>
                        )}
                      </div>

                      {/* 快捷自选备注保存区 */}
                      <div className="space-y-2">
                        <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">个股观察备忘录 (手写证据)</label>
                        <textarea
                          placeholder="在此写下您对该股题材、热点或大阴阳线启动的历史细节观察..."
                          value={selectedStock.remark}
                          onChange={(e) => {
                            const newText = e.target.value;
                            setWatchlist(prev => prev.map(s => s.code === selectedStock.code ? { ...s, remark: newText } : s));
                            setSelectedStock(prev => prev ? { ...prev, remark: newText } : null);
                          }}
                          className="w-full h-20 bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 leading-relaxed"
                        />
                        <div className="text-right">
                          <button
                            onClick={() => handleSaveRemark(selectedStock.code, selectedStock.remark)}
                            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded text-[10px] font-semibold"
                          >
                            保存备忘备注
                          </button>
                        </div>
                      </div>

                      {/* 快速买入面板 */}
                      <div className="flex space-x-2 pt-2">
                        <button
                          onClick={() => openBuyModal(selectedStock)}
                          className="flex-1 py-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-40 text-white rounded text-xs font-bold transition shadow"
                        >
                          记录交易
                        </button>
                        {positions.some(p => p.code === selectedStock.code) && (
                          <button
                            onClick={() => {
                              const pos = positions.find(p => p.code === selectedStock.code);
                              if (pos) openSellModal(pos);
                            }}
                            className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-bold transition shadow"
                          >
                            记录卖出归档
                          </button>
                        )}
                      </div>

                    </div>
                  ) : (
                    <div className="bg-slate-900 border border-slate-800 p-8 rounded-lg text-center text-slate-500 italic">
                      请点击左侧列表中的股票，调阅其高保真日K线及纪律红黄绿灯判定。
                    </div>
                  )}
                </div>

              </div>

            </div>
          )}

          {/* TAB 3: 盘中低吸监控 */}
          {activeTab === "intraday" && (
            <div className="space-y-6">
              
              {/* 今日信号播报 */}
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4 shadow-md">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <div className="flex items-center space-x-2">
                    <TrendingUp className="h-4.5 w-4.5 text-cyan-400" />
                    <h3 className="text-sm font-bold text-slate-200">盘中强回踩低吸监控</h3>
                  </div>
                  <button
                    onClick={handleRefreshQuotes}
                    className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold shadow-md flex items-center space-x-1.5 transition"
                  >
                    <RefreshCw className="h-3.5 w-3.5 animate-spin-hover" />
                    <span>立刻刷新行情</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-3 bg-slate-950/60 border border-slate-850 rounded-lg">
                    <span className="text-[10px] text-slate-500 font-bold block">行情最新同步</span>
                    <span className="text-xs font-mono text-slate-300 mt-1 block">
                      {watchlist[0]?.lastUpdated ? new Date(watchlist[0].lastUpdated).toLocaleTimeString() : "未同步"}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-850 rounded-lg">
                    <span className="text-[10px] text-slate-500 font-bold block">成交额沪深主板前排前30</span>
                    <span className="text-xs font-mono text-slate-300 mt-1 block">已启用主力成交量筛选约束</span>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-850 rounded-lg">
                    <span className="text-[10px] text-slate-500 font-bold block">极简盘中刷新</span>
                    <span className="text-xs text-slate-300 mt-1 block">盘中仅轻量加载价格，保护内存</span>
                  </div>
                </div>
              </div>

              {/* 待买观察候选提示 */}
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4">
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                  <CheckCircle2 className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-xs font-bold uppercase text-slate-200 tracking-wider">待买观察候选 (接近买点: 5日线偏离度 0% ~ 2%)</h3>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  {buyReadyStocks.length === 0 ? (
                    <div className="p-8 text-center text-slate-500 italic bg-slate-950 rounded-lg border border-slate-800/40">
                      盘中暂无进入待买观察层（大阳启动后回踩MA5，偏离度0%~2%且未跌破MA5）的主板股。请点击一键刷新或等待回踩。
                    </div>
                  ) : (
                    buyReadyStocks.map(s => (
                      <div key={s.code} className="p-4 bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-lg flex items-center justify-between transition">
                        <div className="space-y-1">
                          <span className="text-xs font-bold text-slate-200">{s.name} <span className="font-mono text-slate-500 font-normal">{s.code}</span></span>
                          <p className="text-[10px] text-rose-400 font-medium">MA5偏离度: {s.deviation5}% | 5日线: {s.ma5}</p>
                          <p className="text-[11px] text-slate-400 leading-normal">{s.reason}</p>
                        </div>
                        <button
                          onClick={() => openBuyModal(s)}
                          className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs rounded transition shadow"
                        >
                          盘中手动确认
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* 持仓风险监控 */}
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4">
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                  <XCircle className="h-4 w-4 text-rose-500" />
                  <h3 className="text-xs font-bold uppercase text-slate-200 tracking-wider">持仓破位报警区 (现价跌破 5 日线)</h3>
                </div>

                <div className="space-y-3">
                  {positions.filter(p => p.riskLevel === "danger").length === 0 ? (
                    <div className="p-8 text-center text-slate-500 italic bg-slate-950 rounded-lg border border-slate-800/40 text-xs">
                      完美！当前全部持仓股票均稳在 5 日线（MA5）上方。趋势强健。
                    </div>
                  ) : (
                    positions.filter(p => p.riskLevel === "danger").map(p => (
                      <div key={p.code} className="p-4 bg-rose-950/20 border border-rose-900 hover:border-rose-850 rounded-lg flex items-center justify-between transition">
                        <div className="space-y-1">
                          <span className="text-xs font-bold text-rose-400">{p.name} <span className="font-mono text-rose-500 font-normal">{p.code}</span></span>
                          <p className="text-[11px] text-rose-300 font-semibold">5日均线: {p.ma5} | 当前现价: {p.currentPrice} (偏离度: {p.deviation5}%)</p>
                          <p className="text-xs text-rose-400">🚨 指令违规警告：股价已宣告跌破5日生命线！建议毫不留情，果断按纪律执行止损卖出！</p>
                        </div>
                        <button
                          onClick={() => openSellModal(p)}
                          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded transition shadow shrink-0 ml-4"
                        >
                          卖出止损归档
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

            </div>
          )}

          {/* TAB 4: 交易流水审计 */}
          {activeTab === "trades" && (
            <div className="space-y-6">
              
              {/* 今日统计 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">总买入次数</span>
                  <span className="text-2xl font-bold font-mono text-rose-500 block mt-1">{trades.filter(t => t.type === "BUY").length} 次</span>
                  <p className="text-[10px] text-slate-500 mt-2">包含实盘或模拟买入存底</p>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">交易合规率</span>
                  <span className={`text-2xl font-bold font-mono block mt-1 ${auditStats ? (auditStats.complianceRate >= 80 ? "text-rose-500" : "text-amber-500") : "text-slate-400"}`}>
                    {auditStats ? `${auditStats.complianceRate}%` : "未完成"}
                  </span>
                  <p className="text-[10px] text-slate-500 mt-2">买入规则不含违规标签的比例</p>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">全部已实现盈亏</span>
                  <span className={`text-2xl font-bold font-mono block mt-1 ${accountState.realizedPnL >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
                    {accountState.realizedPnL >= 0 ? "+" : ""}{accountState.realizedPnL.toLocaleString()} 元
                  </span>
                  <p className="text-[10px] text-slate-500 mt-2">扣除税费后的净卖出差额</p>
                </div>
              </div>

              {/* 交易审计详细列表 */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <div className="flex items-center space-x-2">
                    <History className="h-4 w-4 text-cyan-400" />
                    <h3 className="text-xs font-bold uppercase text-slate-200 tracking-wider">交易流水账单（交易买卖驱动资产）</h3>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">交易保存前自动触发 watchlist 状态备份</span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 bg-slate-950/40 text-slate-500 font-mono">
                        <th className="p-3">时间</th>
                        <th className="p-3">股票</th>
                        <th className="p-3">方向</th>
                        <th className="p-3 text-right">价格</th>
                        <th className="p-3 text-right">数量</th>
                        <th className="p-3 text-right">总手续费</th>
                        <th className="p-3">纪律合规审计</th>
                        <th className="p-3">买入依据 / 计划备注</th>
                        <th className="p-3">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="p-8 text-center text-slate-500 italic">
                            暂无任何买卖存档记录。可在分组表格点击「买入」进行录入。
                          </td>
                        </tr>
                      ) : (
                        [...trades].reverse().map(t => (
                          <tr key={t.id} className="border-b border-slate-800/40 hover:bg-slate-800/10">
                            <td className="p-3 font-mono text-slate-400">
                              <div>{t.date}</div>
                              <div className="text-[10px] text-slate-500">{t.time}</div>
                            </td>
                            <td className="p-3 font-mono font-bold text-slate-200">
                              <div>{t.name}</div>
                              <div className="text-[10px] text-slate-500">{t.code}</div>
                            </td>
                            <td className="p-3">
                              <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${t.type === "BUY" ? "bg-rose-950 text-rose-400" : "bg-emerald-950 text-emerald-400"}`}>
                                {t.type === "BUY" ? "买入" : "卖出"}
                              </span>
                            </td>
                            <td className="p-3 text-right font-mono font-semibold text-slate-300">{t.price.toFixed(2)}</td>
                            <td className="p-3 text-right font-mono text-slate-400">{t.quantity}</td>
                            <td className="p-3 text-right font-mono text-slate-500" title={`印花税:${t.stampDuty} 佣金:${t.commission} 过户费:${t.transferFee}`}>
                              {t.totalFee.toFixed(2)}
                            </td>
                            <td className="p-3">
                              <div className="space-y-1">
                                <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                  t.rulesConclusion === "符合规则" ? "bg-rose-950 text-rose-400" : "bg-amber-950 text-amber-400"
                                }`}>
                                  {t.rulesConclusion}
                                </span>
                                {t.violationTags && t.violationTags.length > 0 && (
                                  <div className="flex flex-wrap gap-1">
                                    {t.violationTags.map(tag => (
                                      <span key={tag} className="text-[9px] bg-rose-950/40 text-rose-300 px-1 rounded">
                                        {tag}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </td>
                            <td className="p-3 text-slate-400 max-w-xs break-words">
                              <p className="font-semibold text-slate-300">{t.reason}</p>
                              {t.remark && <p className="text-[10px] text-slate-500 mt-1 italic">备注: {t.remark}</p>}
                            </td>
                            <td className="p-3">
                              <div className="flex items-center space-x-1.5">
                                <button
                                  onClick={() => openEditTradeModal(t)}
                                  className="p-1 text-slate-500 hover:text-cyan-400 hover:bg-cyan-950/20 rounded transition"
                                  title="编辑并重新计算费用"
                                >
                                  <Edit className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  onClick={() => handleDeleteTrade(t.id)}
                                  className="p-1 text-slate-500 hover:text-rose-400 hover:bg-rose-955/20 rounded transition"
                                  title="撤销这笔交易"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          )}

          {/* TAB 5: 复盘报告与笔记 */}
          {activeTab === "review" && (
            <div className="space-y-6">
              
              {/* 五大维度闭环复盘导航 */}
              <div className="flex flex-wrap bg-slate-950 p-1 rounded-lg border border-slate-800 gap-1">
                {(["today", "market", "sector", "stock", "action"] as const).map(subTab => (
                  <button
                    key={subTab}
                    onClick={() => setActiveReviewSubTab(subTab)}
                    className={`flex-1 py-2 px-3 text-xs font-bold rounded-md transition duration-150 flex items-center justify-center space-x-1.5 ${
                      activeReviewSubTab === subTab 
                        ? "bg-gradient-to-r from-cyan-600 to-teal-600 text-white shadow-lg" 
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60"
                    }`}
                  >
                    <span>
                      {subTab === "today" ? "📊 今日复盘" :
                       subTab === "market" ? "📈 大盘多空" :
                       subTab === "sector" ? "🔥 板块回踩" :
                       subTab === "stock" ? "🎯 持仓偏差" :
                       "✍️ 纠错自省"}
                    </span>
                  </button>
                ))}
              </div>

              {/* 子视图 1: 今日复盘 */}
              {activeReviewSubTab === "today" && (
                <div className="space-y-6 animate-fade-in">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                      <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">今日买卖次数</span>
                      <span className="text-xl font-bold font-mono text-slate-200 block mt-1">
                        {(todayTrades?.filter((t: any) => t.type === "BUY").length || 0)} 买 / {(todayTrades?.filter((t: any) => t.type === "SELL").length || 0)} 卖
                      </span>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                      <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">今日合规纪律率</span>
                      <span className={`text-xl font-bold font-mono block mt-1 ${
                        complianceRate >= 80 ? "text-rose-500" : "text-amber-500"
                      }`}>
                        {complianceRate}%
                      </span>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                      <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">今日手续费账单</span>
                      <span className="text-xl font-bold font-mono text-cyan-400 block mt-1">
                        {(todayTrades?.reduce((acc: number, t: any) => acc + (t.totalFee || 0), 0) || 0).toFixed(2)} 元
                      </span>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                      <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">今日实现净损益</span>
                      <span className={`text-xl font-bold font-mono block mt-1 ${
                        todayTrades?.reduce((acc: number, t: any) => acc + (t.type === "SELL" ? (t.amount - t.totalFee) : -(t.amount + t.totalFee)), 0) >= 0 
                          ? "text-rose-400" 
                          : "text-emerald-400"
                      }`}>
                        {(todayTrades?.reduce((acc: number, t: any) => acc + (t.type === "SELL" ? (t.amount - t.totalFee) : -(t.amount + t.totalFee)), 0) || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })} 元
                      </span>
                    </div>
                  </div>

                  {/* 违规警告横幅 */}
                  {todayTrades?.some((t: any) => t.rulesConclusion === "违规交易") && (
                    <div className="bg-rose-950/20 border border-rose-900/60 p-4 rounded-lg flex items-start space-x-3 text-rose-300">
                      <ShieldAlert className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
                      <div>
                        <h4 className="text-xs font-bold uppercase tracking-wider text-rose-400">🚨 短线纪律雷达报警：捕获违规硬伤！</h4>
                        <p className="text-[11px] mt-1 text-rose-300 leading-relaxed">
                          今日流水中包含违规买入。例如偏离5日线（MA5）过高、或5日均线仍向下时临时起意买入。硬伤交易会极快稀释您的长期复利！请前往「操作复盘与存档」标签写下深刻反省。
                        </p>
                      </div>
                    </div>
                  )}

                  {/* 今日流水明细 */}
                  <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">今日交易流水审计（数据自动回溯推导持仓）</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead>
                          <tr className="border-b border-slate-800 bg-slate-950/40 text-slate-500 font-mono">
                            <th className="p-3">时间</th>
                            <th className="p-3">股票</th>
                            <th className="p-3">方向</th>
                            <th className="p-3 text-right">价格</th>
                            <th className="p-3 text-right">数量</th>
                            <th className="p-3 text-right">手续费</th>
                            <th className="p-3">审计状态</th>
                            <th className="p-3">反思依据</th>
                          </tr>
                        </thead>
                        <tbody>
                          {!todayTrades || todayTrades.length === 0 ? (
                            <tr>
                              <td colSpan={8} className="p-8 text-center text-slate-500 italic">
                                今日无任何买卖操作。短线空仓也是一种极高雅的操作纪律！
                              </td>
                            </tr>
                          ) : (
                            todayTrades.map((t: any) => (
                              <tr key={t.id} className="border-b border-slate-800/40 hover:bg-slate-800/10">
                                <td className="p-3 font-mono text-slate-400">{t.time}</td>
                                <td className="p-3 font-mono text-slate-200 font-bold">{t.name} ({t.code})</td>
                                <td className="p-3">
                                  <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                    t.type === "BUY" ? "bg-rose-950 text-rose-400" : "bg-emerald-950 text-emerald-400"
                                  }`}>
                                    {t.type === "BUY" ? "买入" : "卖出"}
                                  </span>
                                </td>
                                <td className="p-3 text-right font-mono font-semibold text-slate-300">{t.price.toFixed(2)}</td>
                                <td className="p-3 text-right font-mono text-slate-400">{t.quantity}</td>
                                <td className="p-3 text-right font-mono text-slate-500">{t.totalFee.toFixed(2)}</td>
                                <td className="p-3">
                                  <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                    t.rulesConclusion === "符合规则" ? "bg-rose-950 text-rose-400" : "bg-amber-950 text-amber-400"
                                  }`}>
                                    {t.rulesConclusion}
                                  </span>
                                </td>
                                <td className="p-3 text-slate-400 max-w-xs truncate" title={t.reason}>
                                  {t.reason}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
                         {/* 子视图 2: 大盘复盘 */}
              {activeReviewSubTab === "market" && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in">
                  
                  {/* Left Column: Interactive evaluation */}
                  <div className="lg:col-span-2 bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-5">
                    <div className="border-b border-slate-800 pb-2">
                      <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest">
                        📈 核心指数趋势与资金大普查行动
                      </h3>
                      <p className="text-[11px] text-slate-400 mt-1">请核对上证、深证和创业板指数的走势、成交量及资金动向，确立底层交易水位。</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* 上证综指 */}
                      <div className="bg-slate-950 p-3.5 rounded border border-slate-850 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-extrabold text-slate-200">上证指数</span>
                          <span className="text-[10px] font-mono text-slate-500">000001.SH</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div>
                            <span className="text-[10px] text-slate-500">走势趋势:</span>
                            <select value={shTrend} onChange={(e) => setShTrend(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="向上">向上 (多头主导)</option>
                              <option value="震荡">震荡 (均线粘合)</option>
                              <option value="向下">向下 (破位防踩)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">成交量能:</span>
                            <select value={shVolume} onChange={(e) => setShVolume(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="放量">放量 (资金活跃)</option>
                              <option value="缩量">缩量 (追高谨慎)</option>
                              <option value="持平">持平 (存量博弈)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">资金流向:</span>
                            <select value={shFlow} onChange={(e) => setShFlow(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="净流入">资金主力净流入</option>
                              <option value="净流出">资金主力净流出</option>
                            </select>
                          </div>
                        </div>
                      </div>

                      {/* 深证成指 */}
                      <div className="bg-slate-950 p-3.5 rounded border border-slate-850 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-extrabold text-slate-200">深证成指</span>
                          <span className="text-[10px] font-mono text-slate-500">399001.SZ</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div>
                            <span className="text-[10px] text-slate-500">走势趋势:</span>
                            <select value={szTrend} onChange={(e) => setSzTrend(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="向上">向上 (多头主导)</option>
                              <option value="震荡">震荡 (均线粘合)</option>
                              <option value="向下">向下 (破位防踩)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">成交量能:</span>
                            <select value={szVolume} onChange={(e) => setSzVolume(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="放量">放量 (资金活跃)</option>
                              <option value="缩量">缩量 (追高谨慎)</option>
                              <option value="持平">持平 (存量博弈)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">资金流向:</span>
                            <select value={szFlow} onChange={(e) => setSzFlow(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="净流入">资金主力净流入</option>
                              <option value="净流出">资金主力净流出</option>
                            </select>
                          </div>
                        </div>
                      </div>

                      {/* 创业板指 */}
                      <div className="bg-slate-950 p-3.5 rounded border border-slate-850 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-extrabold text-slate-200">创业板指</span>
                          <span className="text-[10px] font-mono text-slate-500">399006.SZ</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div>
                            <span className="text-[10px] text-slate-500">走势趋势:</span>
                            <select value={cyTrend} onChange={(e) => setCyTrend(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="向上">向上 (多头主导)</option>
                              <option value="震荡">震荡 (均线粘合)</option>
                              <option value="向下">向下 (破位防踩)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">成交量能:</span>
                            <select value={cyVolume} onChange={(e) => setCyVolume(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="放量">放量 (资金活跃)</option>
                              <option value="缩量">缩量 (追高谨慎)</option>
                              <option value="持平">持平 (存量博弈)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">资金流向:</span>
                            <select value={cyFlow} onChange={(e) => setCyFlow(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="净流入">资金主力净流入</option>
                              <option value="净流出">资金主力净流出</option>
                            </select>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 系统性大盘风险判定 */}
                    <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                      <div className="space-y-1">
                        <span className="text-xs font-extrabold text-slate-200">🚦 判定今日市场是否遇系统性见顶/大阴大跌风险？</span>
                        <p className="text-[11px] text-slate-400">大盘出现系统性下踩时，必须提高止损警戒水位，收紧底仓浮亏度。</p>
                      </div>
                      <div className="flex items-center space-x-3 shrink-0">
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input 
                            type="checkbox" 
                            checked={systemicRisk} 
                            onChange={(e) => {
                              setSystemicRisk(e.target.checked);
                              logAction(e.target.checked ? "⚠️ 警报：手动确认系统性风险，单股最大止损点自动调高至 7%~8%！" : "✓ 提示：解除系统性风险状态，单股最大止损位恢复至正常的 9%~10%");
                            }}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-300 after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-rose-600"></div>
                        </label>
                        <span className={`text-xs font-black ${systemicRisk ? "text-rose-500 animate-pulse" : "text-slate-500"}`}>
                          {systemicRisk ? "【已触发】系统性风险状态" : "【正常】无系统性风险"}
                        </span>
                      </div>
                    </div>

                    {/* 联动止损上调报警 */}
                    {systemicRisk && (
                      <div className="bg-rose-950/40 border border-rose-900 p-4 rounded-lg text-rose-200 flex items-start space-x-3 shadow-md">
                        <ShieldAlert className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
                        <div>
                          <h4 className="text-xs font-black uppercase text-rose-400">🚨 止损风控铁律升级警报</h4>
                          <p className="text-[11px] mt-1 text-rose-300 leading-normal">
                            当前已手动确认触发系统性大盘风险！依据交易止损与盈利优化策略：<b>单股止损水位由原 9-10% 自动上调收紧至 7-8%！以防范极端踩踏，死守本金！</b>
                          </p>
                          <p className="text-[10px] mt-1 text-slate-400 font-medium">请立即核对持仓，如有股票跌破5日线且亏损触及 7%-8%，14:50 前必须无条件清仓！</p>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right Column: Static gauge & advise */}
                  <div className="col-span-1 space-y-4">
                    <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg flex flex-col items-center justify-center text-center space-y-4 shadow">
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                        多空强度综合指数
                      </span>

                      {/* 圆形仪表盘 */}
                      <div className="relative flex items-center justify-center">
                        <svg className="w-32 h-32 transform -rotate-90">
                          <circle
                            cx="64"
                            cy="64"
                            r="50"
                            className="stroke-slate-850"
                            strokeWidth="8"
                            fill="transparent"
                          />
                          <circle
                            cx="64"
                            cy="64"
                            r="50"
                            className="stroke-cyan-500 transition-all duration-500"
                            strokeWidth="8"
                            fill="transparent"
                            strokeDasharray={314}
                            strokeDashoffset={314 - (314 * (systemicRisk ? 20 : (reportContext?.marketSnapshot?.bullishIndex || 55))) / 100}
                          />
                        </svg>
                        <div className="absolute flex flex-col items-center">
                          <span className="text-3xl font-mono font-black text-cyan-400">
                            {systemicRisk ? 20 : (reportContext?.marketSnapshot?.bullishIndex || 55)}%
                          </span>
                          <span className="text-[9px] text-slate-500">多头仓位上限建议</span>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <span className="text-xs font-bold text-slate-300">多空评级: </span>
                        <span className={`text-xs font-black px-2 py-0.5 rounded ${
                          systemicRisk 
                            ? "bg-rose-950 text-rose-400" 
                            : "bg-amber-950 text-amber-400"
                        }`}>
                          {systemicRisk 
                            ? "大盘高危风控状态 (严格控仓或空仓)" 
                            : "震荡回踩期 (控制底仓低吸)"}
                        </span>
                      </div>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-2">
                      <h4 className="text-xs font-extrabold text-slate-300">上证、深证及创业板复盘硬指标</h4>
                      <p className="text-[11px] text-slate-400 leading-normal">
                        若遇系统性风险（例如主力资金呈断崖式净流出、多指数破位MA5），止损硬限必须从9%-10%上调收紧至7%-8%，以第三方冷静逻辑阻断扛单行为。
                      </p>
                    </div>
                  </div>

                </div>
              )}

              {/* 子视图 3: 板块复盘 */}
              {activeReviewSubTab === "sector" && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in">
                  
                  {/* Left Column: 50 ETF Checker */}
                  <div className="lg:col-span-2 bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                    <div className="border-b border-slate-800 pb-2 flex items-center justify-between">
                      <div className="space-y-0.5">
                        <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center space-x-1.5">
                          <span>🔥 50只行业板块 ETF 趋势及资金多头大复盘</span>
                        </h3>
                        <p className="text-[11px] text-slate-400">拉网式大复盘 50 个行业 ETF 的主力资金流向与五日生命线排列，锁定最热强势回踩板块。</p>
                      </div>
                      <div className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-center shrink-0">
                        <span className="text-[10px] text-slate-500 block">今日扫过标的</span>
                        <span className="text-xs font-mono font-black text-cyan-400">{reviewedEtfCount} / 50 只</span>
                      </div>
                    </div>

                    {/* ETF 扫描进度及一键拉网按钮 */}
                    <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
                      <div className="space-y-1.5 w-full sm:w-auto">
                        <span className="text-xs font-bold text-slate-200 block">行业 ETF 多空能量网筛选进度</span>
                        <div className="w-full sm:w-64 bg-slate-900 rounded-full h-2.5 border border-slate-800 overflow-hidden">
                          <div 
                            className="bg-cyan-500 h-2.5 rounded-full transition-all duration-300" 
                            style={{ width: `${(reviewedEtfCount / 50) * 100}%` }}
                          ></div>
                        </div>
                      </div>
                      <button 
                        onClick={() => {
                          setReviewedEtfCount(50);
                          logAction("✅ 成功拉网复盘全市场 50 个主流行业 ETF！已记录主力成交及资金承接风口。");
                        }}
                        className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-800/40 rounded text-xs font-bold transition shadow cursor-pointer"
                      >
                        ⚡ 快速一键拉网已复盘 50 个主流 ETF
                      </button>
                    </div>

                    {/* 代表性行业 ETF 观察清单 */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                      {[
                        { code: "512480", name: "半导体 ETF" },
                        { code: "515030", name: "新能源车 ETF" },
                        { code: "512010", name: "医药医疗 ETF" },
                        { code: "512880", name: "大证券 ETF" },
                        { code: "159869", name: "动漫游戏 ETF" },
                        { code: "512660", name: "高端军工 ETF" },
                        { code: "515220", name: "红利煤炭 ETF" },
                        { code: "515060", name: "重整房地产 ETF" },
                      ].map((etf, i) => (
                        <div key={i} className="p-3 bg-slate-950 border border-slate-850 rounded flex items-center justify-between hover:border-slate-700">
                          <div className="space-y-0.5">
                            <span className="text-slate-500 block text-[9px] font-mono">{etf.code}</span>
                            <span className="font-bold text-slate-300">{etf.name}</span>
                          </div>
                          <span className="text-[10px] bg-cyan-950/40 text-cyan-400 border border-cyan-900/40 px-1.5 py-0.5 rounded font-bold">
                            已阅趋势
                          </span>
                        </div>
                      ))}
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-black text-slate-500 uppercase block tracking-wider">
                        概念及板块热度榜参考 (大智慧/同花顺人气榜前排)
                      </label>
                      <input 
                        type="text" 
                        value={hotSectors}
                        onChange={(e) => setHotSectors(e.target.value)}
                        placeholder="例如: 固态电池、AI算力大容量高人气、低空经济、证券红利低估重估支撑"
                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500"
                      />
                    </div>
                  </div>

                  {/* Right Column: Sector Notes */}
                  <div className="col-span-1 bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider border-b border-slate-800 pb-2">
                      行业板块资金规律备忘
                    </h3>
                    <div className="space-y-3">
                      <div>
                        <label className="text-[10px] font-black text-slate-500 block tracking-wider uppercase">主力板块资金流入与承接共振观察</label>
                        <textarea
                          rows={6}
                          value={etfFlowNotes}
                          onChange={(e) => setEtfFlowNotes(e.target.value)}
                          placeholder="例如: 今日半导体及大金融主力资金有深度共振，ETF呈大幅度净流入。科技回踩五日均线形成强力托底，符合强势回踩做多期。"
                          className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500 leading-relaxed"
                        />
                      </div>
                      <div className="p-3.5 bg-slate-950 border border-slate-850 rounded text-[11px] text-slate-400 space-y-1.5">
                        <span className="font-bold text-slate-300 block">💡 行业 ETF 交易指引:</span>
                        <span>做超短线必须做到「板块护航，个股突围」。只要大板块趋势向上且没有见顶断崖，旗下强势股的回踩五日线行为便是安全的黄金买入段。</span>
                      </div>
                    </div>
                  </div>

                </div>
              )}

              {/* 子视图 4: 个股复盘 */}
              {activeReviewSubTab === "stock" && (
                <div className="space-y-6 animate-fade-in">
                  
                  {/* Step 1 to 3: Global Stock Screen Wizards */}
                  <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-5">
                    <div className="border-b border-slate-800 pb-2">
                      <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest">
                        🎯 全市场流动性前排、暴量突围股、涨跌停板拉网大筛选
                      </h3>
                      <p className="text-[11px] text-slate-400 mt-1">这套严格的标准化流程不仅能帮您过滤出真正的流动性龙虎种子，更能彻底杜绝盲目盘中跟风。</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* 步骤 1 */}
                      <div className={`p-4 rounded-lg border transition ${top200Reviewed ? "bg-cyan-950/15 border-cyan-800/40" : "bg-slate-950 border-slate-850"}`}>
                        <div className="flex items-start justify-between">
                          <span className="text-[10px] bg-slate-900 text-slate-400 px-2 py-0.5 rounded font-bold font-mono">步骤 1</span>
                          <input 
                            type="checkbox" 
                            checked={top200Reviewed} 
                            onChange={(e) => setTop200Reviewed(e.target.checked)}
                            className="rounded text-cyan-600 focus:ring-0 focus:ring-offset-0 bg-slate-900 border-slate-800 cursor-pointer"
                          />
                        </div>
                        <h4 className="text-xs font-black text-slate-200 mt-2">成交额降序前 200 股扫描</h4>
                        <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                          按全市场昨日成交额由大到小排序，精扫前 200 只股票。剔除僵尸、锁定最强流动性人气大资金池。
                        </p>
                        <span className="text-[10px] text-cyan-400 block mt-2 font-bold">{top200Reviewed ? "✓ 已按成交前200筛选完毕" : "⏳ 待勾选确认"}</span>
                      </div>

                      {/* 步骤 2 */}
                      <div className={`p-4 rounded-lg border transition ${volRatioReviewed ? "bg-cyan-950/15 border-cyan-800/40" : "bg-slate-950 border-slate-850"}`}>
                        <div className="flex items-start justify-between">
                          <span className="text-[10px] bg-slate-900 text-slate-400 px-2 py-0.5 rounded font-bold font-mono">步骤 2</span>
                          <input 
                            type="checkbox" 
                            checked={volRatioReviewed} 
                            onChange={(e) => setVolRatioReviewed(e.target.checked)}
                            className="rounded text-cyan-600 focus:ring-0 focus:ring-offset-0 bg-slate-900 border-slate-800 cursor-pointer"
                          />
                        </div>
                        <h4 className="text-xs font-black text-slate-200 mt-2">量比前 50 且成交在 10~20亿</h4>
                        <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                          精确复盘当日量比前 50 且成交额在 10 亿 ~ 20 亿以上的放量突围股，捕捉爆量异动主力。
                        </p>
                        <span className="text-[10px] text-cyan-400 block mt-2 font-bold">{volRatioReviewed ? "✓ 已按量比与10-20亿级筛选" : "⏳ 待勾选确认"}</span>
                      </div>

                      {/* 步骤 3 */}
                      <div className={`p-4 rounded-lg border transition ${limitUpReviewed ? "bg-cyan-950/15 border-cyan-800/40" : "bg-slate-950 border-slate-850"}`}>
                        <div className="flex items-start justify-between">
                          <span className="text-[10px] bg-slate-900 text-slate-400 px-2 py-0.5 rounded font-bold font-mono">步骤 3</span>
                          <input 
                            type="checkbox" 
                            checked={limitUpReviewed} 
                            onChange={(e) => setLimitUpReviewed(e.target.checked)}
                            className="rounded text-cyan-600 focus:ring-0 focus:ring-offset-0 bg-slate-900 border-slate-800 cursor-pointer"
                          />
                        </div>
                        <h4 className="text-xs font-black text-slate-200 mt-2">当日涨跌停板股票核查</h4>
                        <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                          扫描核查当日所有涨停及跌停个股。拆解龙头股连板高度、封板溢价率及市场最热门主线题材。
                        </p>
                        <span className="text-[10px] text-cyan-400 block mt-2 font-bold">{limitUpReviewed ? "✓ 已核对当日涨跌停板高度" : "⏳ 待勾选确认"}</span>
                      </div>
                    </div>
                  </div>

                  {/* Step 4: Objective diagnostics on watchlist and positions */}
                  <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                    <div className="border-b border-slate-800 pb-2 flex flex-col md:flex-row md:items-center justify-between gap-2">
                      <div className="space-y-0.5">
                        <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center space-x-1.5">
                          <span>🕵️ 步骤 4：以纯第三方冷静视角诊断自选与持仓 (强力破除屁股决定脑袋执念)</span>
                        </h3>
                        <p className="text-[11px] text-slate-400">请无视自己的买入成本、盈亏心理状态。假设您没有任何头寸，以极度客观的第三方视角判定此股应坚守或是必须割肉退出。</p>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">
                        共有 {diagnosedHoldings.length} 只标的列席诊断
                      </span>
                    </div>

                    {diagnosedHoldings.length === 0 ? (
                      <div className="p-8 text-center text-slate-500 italic bg-slate-950 rounded border border-slate-850 text-xs">
                        当前自选股或持仓为空，无法启动诊断。可在「今日看板」快捷补录买入，数据会自动加载于此！
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {diagnosedHoldings.map((diag, idx) => (
                          <div key={diag.code} className="bg-slate-950 p-4 rounded-lg border border-slate-850 grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                            <div className="space-y-1">
                              <span className="text-xs font-mono font-black text-slate-200 block">{diag.name} ({diag.code})</span>
                              <div className="flex items-center space-x-2">
                                <span className="text-[10px] text-slate-500">五日均线上方占比/生命线状态:</span>
                                <span className="text-[10px] bg-slate-900 text-cyan-300 font-bold px-1.5 rounded">健康监视</span>
                              </div>
                            </div>
                            
                            {/* Diagnosis option dropdown */}
                            <div>
                              <label className="text-[9px] text-slate-500 uppercase block tracking-wider mb-1">第三方立场客观判定结论</label>
                              <select 
                                value={diag.judgment} 
                                onChange={(e) => {
                                  const updated = [...diagnosedHoldings];
                                  updated[idx].judgment = e.target.value;
                                  setDiagnosedHoldings(updated);
                                }}
                                className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-300 focus:outline-none"
                              >
                                <option value="第三方客观评估：买点完好，无理由坚定持有">✅ 买点成立，生命线支撑有力，持有</option>
                                <option value="第三方客观评估：破位跌破5日线，必须割肉清仓">🚨 已经破位MA5，必须毫不手软清仓割肉</option>
                                <option value="第三方客观评估：未有跌破但三天未冲高，应微亏调仓">⏳ 连续3日未收回，符合时间淘汰机制，退出</option>
                                <option value="第三方客观评估：距均线乖离过大，看分批止盈锁定盈利">💰 乖离过大远离MA5，无贪婪锁定高位浮盈</option>
                              </select>
                            </div>

                            {/* Plan input */}
                            <div>
                              <label className="text-[9px] text-slate-500 uppercase block tracking-wider mb-1">明日操盘硬性执行口令</label>
                              <input 
                                type="text"
                                value={diag.actionPlan}
                                onChange={(e) => {
                                  const updated = [...diagnosedHoldings];
                                  updated[idx].actionPlan = e.target.value;
                                  setDiagnosedHoldings(updated);
                                }}
                                placeholder="例如: 9:35破5日线无多头承接必须坚决退出，不抱幻想"
                                className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* 子视图 5: 操作复盘与存档 */}
              {activeReviewSubTab === "action" && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start animate-fade-in">
                  {/* 书写心得 */}
                  <div className="lg:col-span-1 bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4">
                    <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                      <BookOpen className="h-4 w-4 text-cyan-400" />
                      <h3 className="text-xs font-bold uppercase text-slate-200 tracking-wider">保存复盘日记归档</h3>
                    </div>

                    <div className="space-y-3">
                      <div>
                        <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">复盘时间维度</label>
                        <div className="flex bg-slate-950 p-1 rounded border border-slate-800 mt-1">
                          {(["daily", "weekly", "monthly"] as const).map(t => (
                            <button
                              key={t}
                              onClick={() => setReviewType(t)}
                              className={`flex-1 py-1 text-[10px] font-bold rounded transition ${reviewType === t ? "bg-slate-800 text-cyan-400" : "text-slate-500 hover:text-slate-300"}`}
                            >
                              {t === "daily" ? "日报" : t === "weekly" ? "周报" : "月报"}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div>
                        <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">复盘参考日期</label>
                        <input
                          type="date"
                          value={reportDate}
                          onChange={(e) => setReportDate(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs font-mono text-slate-300 mt-1 focus:outline-none focus:border-cyan-500"
                        />
                      </div>

                      <div>
                        <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">今日违规诊断与纠错面反思</label>
                        <textarea
                          rows={6}
                          value={reportSummary}
                          onChange={(e) => setReportSummary(e.target.value)}
                          placeholder="分析今日买卖，纠错乱买违纪，如何消灭盘中情绪下单？有哪些大阳线标的符合昨日计划..."
                          className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500 leading-relaxed"
                        />
                      </div>

                      <div>
                        <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">明日严苛作战行动计划 (拒绝临时决策)</label>
                        <textarea
                          rows={4}
                          value={reportPlan}
                          onChange={(e) => setReportPlan(e.target.value)}
                          placeholder="唯一允许观察的对象，买入等待位置，持仓在均线破位时的清仓计划..."
                          className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500 leading-relaxed"
                        />
                      </div>

                      <button
                        onClick={handleSaveReport}
                        className="w-full py-2 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white font-bold text-xs rounded transition shadow"
                      >
                        一键保存复盘报告并归档笔记本
                      </button>
                    </div>
                  </div>

                  {/* 历史复盘档案笔记本 */}
                  <div className="lg:col-span-2 bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                      <div className="flex items-center space-x-2">
                        <FileText className="h-4 w-4 text-cyan-400" />
                        <h3 className="text-xs font-bold uppercase text-slate-200 tracking-wider">
                          历史{reviewType === "daily" ? "日" : reviewType === "weekly" ? "周" : "月"}复盘笔记本
                        </h3>
                      </div>
                    </div>

                    <div className="space-y-4">
                      {reportsList.length === 0 ? (
                        <div className="p-12 text-center text-slate-500 italic bg-slate-950 rounded-lg border border-slate-800/40 text-xs">
                          暂无任何历史复盘记录。
                        </div>
                      ) : (
                        reportsList.map(rep => (
                          <div key={rep.id} className="bg-slate-950 border border-slate-800/60 p-4 rounded-lg space-y-3">
                            <div className="flex flex-wrap items-center justify-between border-b border-slate-850 pb-2">
                              <span className="text-xs font-bold font-mono text-cyan-400 flex items-center space-x-1.5">
                                <Calendar className="h-3.5 w-3.5" />
                                <span>{rep.date} 复盘归档</span>
                              </span>
                              <span className="text-[10px] text-slate-500 font-mono">归档时间: {rep.createdTime}</span>
                            </div>

                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
                              <div className="p-2 bg-slate-900/60 rounded border border-slate-800">
                                <span className="text-[9px] text-slate-500 block">买入/卖出</span>
                                <span className="text-xs font-bold text-slate-300 font-mono">{rep.buyCount}次 / {rep.sellCount}次</span>
                              </div>
                              <div className="p-2 bg-slate-900/60 rounded border border-slate-800">
                                <span className="text-[9px] text-slate-500 block">合规率</span>
                                <span className={`text-xs font-bold font-mono ${rep.ruleComplianceRate >= 80 ? "text-rose-500" : "text-amber-500"}`}>
                                  {rep.ruleComplianceRate}%
                                </span>
                              </div>
                              <div className="p-2 bg-slate-900/60 rounded border border-slate-800">
                                <span className="text-[9px] text-slate-500 block">实现损益</span>
                                <span className={`text-xs font-bold font-mono ${rep.realizedPnL >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
                                  {rep.realizedPnL >= 0 ? "+" : ""}{rep.realizedPnL.toLocaleString()}
                                </span>
                              </div>
                              <div className="p-2 bg-slate-900/60 rounded border border-slate-800">
                                <span className="text-[9px] text-slate-500 block">账户风控状态</span>
                                <span className="text-xs font-bold text-slate-300">{rep.portfolioRisk.split(" ")[0]}</span>
                              </div>
                            </div>

                            <div className="space-y-1.5 text-xs">
                              <h4 className="font-bold text-slate-300">💡 纠错与纪律心魔：</h4>
                              <p className="text-slate-400 leading-normal pl-2 border-l border-cyan-500/30 whitespace-pre-wrap">{rep.summary}</p>
                            </div>

                            {rep.tomorrowPlan && (
                              <div className="space-y-1.5 text-xs pt-1 border-t border-slate-900">
                                <h4 className="font-bold text-slate-300">🎯 明日作战操盘计划：</h4>
                                <p className="text-slate-400 leading-normal pl-2 border-l border-teal-500/30 whitespace-pre-wrap">{rep.tomorrowPlan}</p>
                              </div>
                            )}

                            {rep.violations && rep.violations.length > 0 && (
                              <div className="pt-2 border-t border-slate-900 flex flex-wrap gap-1.5 items-center">
                                <span className="text-[10px] font-bold text-rose-500 uppercase">捕获违规细节:</span>
                                {rep.violations.map((v, i) => (
                                  <span key={i} className="text-[9px] bg-rose-950/40 text-rose-300 px-1.5 py-0.5 rounded">
                                    {v}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                </div>
              )}

            </div>
          )}

          {/* TAB 6: 账户系统设置 */}
          {activeTab === "settings" && (
            <div className="max-w-2xl mx-auto space-y-6">
              
              <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                  <Coins className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-slate-200">交易系统手续费率配置</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">券商佣金比例 (双向收取)</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={feeSettings.commissionRate}
                      onChange={(e) => setFeeSettings(p => ({ ...p, commissionRate: Number(e.target.value) }))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-slate-500 block mt-1">例如: 0.0003 代表万分之三</span>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">单笔佣金最低起征点 (元)</label>
                    <input
                      type="number"
                      step="1"
                      value={feeSettings.minCommission}
                      onChange={(e) => setFeeSettings(p => ({ ...p, minCommission: Number(e.target.value) }))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-slate-500 block mt-1">不足此金额按此值收取 (标准 A股 为 5.0)</span>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">印花税比例 (仅在卖出收取)</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={feeSettings.stampDutyRate}
                      onChange={(e) => setFeeSettings(p => ({ ...p, stampDutyRate: Number(e.target.value) }))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-slate-500 block mt-1">例如: 0.0005 代表千分之零点五</span>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">过户费比例 (双向收取)</label>
                    <input
                      type="number"
                      step="0.00001"
                      value={feeSettings.transferFeeRate}
                      onChange={(e) => setFeeSettings(p => ({ ...p, transferFeeRate: Number(e.target.value) }))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-slate-500 block mt-1">例如: 0.00001 代表十万分之一</span>
                  </div>
                </div>

                <div className="text-right pt-2 border-t border-slate-800/60">
                  <button
                    onClick={() => handleSaveFees(feeSettings)}
                    className="px-4 py-2 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white rounded text-xs font-semibold shadow transition"
                  >
                    保存并应用手续费率
                  </button>
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                  <Settings className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-slate-200">
                    {currentMode === "real" ? "实盘交易账户设置" : "模拟交易账户设置"}
                  </h3>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">
                      {currentMode === "real" ? "调整实盘初始总本金 (元)" : "调整模拟初始总本金 (元)"}
                    </label>
                    <p className="text-[10px] text-slate-500 mb-2">
                      {currentMode === "real" 
                        ? "更改后，系统的实盘可用现金与实盘已实现盈亏将根据您的实盘交易历史重新计算。" 
                        : "更改后，系统的模拟可用现金与模拟已实现盈亏将根据您的模拟交易历史重新计算。"}
                    </p>
                    <div className="flex space-x-2">
                      <input
                        type="number"
                        value={accountState.initialCash}
                        readOnly
                        className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-400 focus:outline-none"
                      />
                      <button
                        onClick={handleResetCash}
                        className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold"
                      >
                        手动修改
                      </button>
                    </div>
                  </div>

                  <div className="border-t border-slate-800 pt-4">
                    <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">文件与数据同步校验</h4>
                    <div className="bg-slate-950 p-4 rounded border border-slate-850 font-mono text-xs space-y-2 text-slate-400">
                      <div><span className="text-slate-500">Watchlist文件：</span>data/watchlist.csv</div>
                      <div><span className="text-slate-500">交易流水文件：</span>data/trades/trade_log.csv</div>
                      <div><span className="text-slate-500">历史均线缓存：</span>data/history/*.csv (个股历史K线)</div>
                      <div><span className="text-slate-500">报告归档位置：</span>data/reports/*</div>
                      <div><span className="text-slate-500">自动备份地址：</span>data/backups/ (写入前自动触发)</div>
                    </div>
                  </div>

                  <div className="border-t border-slate-800 pt-4 flex space-x-3">
                    <button
                      onClick={() => {
                        if (confirm("是否清空所有自选股票并重置股票池？")) {
                          fetch("/api/watchlist/generate", { method: "POST" })
                            .then(() => {
                              logAction("⚙️ 系统数据初始化完成！");
                              loadAllData();
                            });
                        }
                      }}
                      className="px-3.5 py-2 bg-slate-800 hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 border border-slate-700 hover:border-rose-900 rounded text-xs font-semibold transition"
                    >
                      恢复股票自选池
                    </button>
                    <button
                      onClick={() => {
                        if (confirm("这会清空你所有的交易流水，确认彻底重置资产和账户流水吗？")) {
                          fetch("/api/trades/delete", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ id: "ALL" }) // 如果有该路由
                          }).finally(() => {
                            logAction("⚙️ 账户数据已重置。");
                            loadAllData();
                          });
                        }
                      }}
                      className="px-3.5 py-2 bg-slate-800 hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 border border-slate-700 hover:border-rose-900 rounded text-xs font-semibold transition"
                    >
                      清空交易流水
                    </button>
                  </div>

                </div>
              </div>

            </div>
          )}

        </main>
      </div>

      {/* 交易确认及纪律合规模态框 (Modal) */}
      {showTradeModal && tradeTarget && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-lg w-full p-6 space-y-4 shadow-2xl overflow-y-auto max-h-[90vh]">
            
            {/* 头 */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200">
                录入{tradeType === "BUY" ? "买入" : "卖出"}交易记录 ({tradeTarget.name})
              </h3>
              <button
                onClick={() => setShowTradeModal(false)}
                className="text-slate-500 hover:text-slate-300"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            {/* 极简实时纪律审计指示灯 */}
            {tradeType === "BUY" && (
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-850 space-y-2">
                <span className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">实时纪律雷达监控</span>
                
                {/* 板块/大阳线/MA5 诊断 */}
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${isMainBoard(tradeTarget.code) ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">沪深主板: {isMainBoard(tradeTarget.code) ? "满足" : "不符"}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${tradeTarget.bigCandlePct >= 5.0 ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">20日大阳: {tradeTarget.bigCandlePct >= 5.0 ? "有" : "无"}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${tradeTarget.ma5Upward ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">MA5向上: {tradeTarget.ma5Upward ? "满足" : "不符"}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${tradePrice <= (tradeTarget.ma5 * 1.02) && tradePrice >= tradeTarget.ma5 ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">0%~2%偏离: {tradePrice <= (tradeTarget.ma5 * 1.02) && tradePrice >= tradeTarget.ma5 ? "满足" : "不符"}</span>
                  </div>
                </div>

                {/* 违规警告 */}
                {tradeType === "BUY" && (tradePrice > (tradeTarget.ma5 * 1.02) || tradePrice < tradeTarget.ma5 || tradeTarget.bigCandlePct < 5.0 || !tradeTarget.ma5Upward || !isMainBoard(tradeTarget.code)) && (
                  <p className="text-[10px] text-amber-500 italic leading-normal border-t border-slate-900 pt-1.5">
                    ⚠️ 警告：当前录入数据在纪律上存在违规买入风险（无5%阳线启动、MA5未向上、非偏离金区或已跌破MA5）。继续录入将产生红字违规证据，并归档至审计中心。
                  </p>
                )}
              </div>
            )}

            {/* 交易录入表单 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易方向</label>
                <div className="flex bg-slate-950 p-1 rounded border border-slate-800 mt-1">
                  <button
                    onClick={() => setTradeType("BUY")}
                    className={`flex-1 py-1 text-xs font-bold rounded transition ${tradeType === "BUY" ? "bg-rose-950 text-rose-400" : "text-slate-500"}`}
                  >
                    买入 (BUY)
                  </button>
                  <button
                    onClick={() => setTradeType("SELL")}
                    className={`flex-1 py-1 text-xs font-bold rounded transition ${tradeType === "SELL" ? "bg-emerald-950 text-emerald-400" : "text-slate-500"}`}
                  >
                    卖出 (SELL)
                  </button>
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易价格 (元)</label>
                <input
                  type="number"
                  step="0.01"
                  value={tradePrice}
                  onChange={(e) => setTradePrice(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs font-mono text-slate-200 mt-1 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易数量 (股)</label>
                <input
                  type="number"
                  step="100"
                  value={tradeQuantity}
                  onChange={(e) => setTradeQuantity(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs font-mono text-slate-200 mt-1 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">一手价格合计</label>
                <div className="p-2 bg-slate-950 rounded border border-slate-800 mt-1 text-xs font-mono font-bold text-slate-300">
                  {(tradePrice * tradeQuantity).toLocaleString(undefined, { minimumFractionDigits: 2 })} 元
                </div>
              </div>
            </div>

            {/* 预计税费卡片 */}
            <div className="bg-slate-950 p-3 rounded border border-slate-850 text-[10px] font-mono text-slate-500 space-y-1">
              <div className="flex justify-between">
                <span>印花税 (0.05%, 仅卖出):</span>
                <span>{est.stamp.toFixed(2)} 元</span>
              </div>
              <div className="flex justify-between">
                <span>券商佣金 (0.03%, 最低5元):</span>
                <span>{est.comm.toFixed(2)} 元</span>
              </div>
              <div className="flex justify-between">
                <span>过户费 (0.002%):</span>
                <span>{est.trans.toFixed(2)} 元</span>
              </div>
              <div className="flex justify-between border-t border-slate-900 pt-1 text-slate-400 font-bold">
                <span>预计净结算金额 ({tradeType === "BUY" ? "实际付出" : "实际到账"}):</span>
                <span className={tradeType === "BUY" ? "text-rose-400" : "text-emerald-400"}>
                  {est.settle.toLocaleString(undefined, { minimumFractionDigits: 2 })} 元
                </span>
              </div>
            </div>

            {/* 强制反思书写 */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">
                操盘原因与决策证据 (纪律约束：拒绝临时意念下单)
              </label>
              <textarea
                rows={2}
                value={tradeReason}
                onChange={(e) => setTradeReason(e.target.value)}
                placeholder="为什么买/卖它？5日线偏离度是多少？是否符合大阳拉升？如果是违规买入，请写下原因反思..."
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 leading-normal"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">流水备注 (备用)</label>
              <input
                type="text"
                value={tradeRemark}
                onChange={(e) => setTradeRemark(e.target.value)}
                placeholder="实盘/模拟 归档单号等备注"
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* 执行 */}
            <button
              onClick={handleExecuteTrade}
              className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs rounded transition shadow"
            >
              确认并录入交易账簿
            </button>

          </div>
        </div>
      )}

      {/* 编辑交易记录模态框 */}
      {editingTrade && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-lg w-full p-6 space-y-4 shadow-2xl overflow-y-auto max-h-[90vh]">
            
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200">
                编辑交易流水记录 (ID: {editingTrade.id.substring(0, 8)}...)
              </h3>
              <button
                onClick={() => setEditingTrade(null)}
                className="text-slate-500 hover:text-slate-300"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">代码/名称</label>
                <div className="p-2 bg-slate-950 rounded border border-slate-850 mt-1 text-xs text-slate-400 font-mono font-bold">
                  {editingTrade.code} - {editingTrade.name} ({editingTrade.type === "BUY" ? "买入" : "卖出"})
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易时间</label>
                <div className="flex space-x-1.5 mt-1">
                  <input
                    type="date"
                    value={editDate}
                    onChange={(e) => setEditDate(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-850 rounded p-1.5 text-xs font-mono text-slate-200 focus:outline-none"
                  />
                  <input
                    type="text"
                    value={editTime}
                    onChange={(e) => setEditTime(e.target.value)}
                    placeholder="14:30:00"
                    className="w-24 bg-slate-950 border border-slate-850 rounded p-1.5 text-xs font-mono text-slate-200 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易价格 (元)</label>
                <input
                  type="number"
                  step="0.01"
                  value={editPrice}
                  onChange={(e) => {
                    const price = Number(e.target.value);
                    setEditPrice(price);
                    const amt = price * editQuantity;
                    const comm = Math.max(feeSettings.minCommission, Number((amt * feeSettings.commissionRate).toFixed(2)));
                    const trans = Number((amt * feeSettings.transferFeeRate).toFixed(2));
                    const stamp = editingTrade.type === "SELL" ? Number((amt * feeSettings.stampDutyRate).toFixed(2)) : 0;
                    setEditCommission(comm);
                    setEditTransferFee(trans);
                    setEditStampDuty(stamp);
                  }}
                  className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs font-mono text-slate-200 mt-1 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易数量 (股)</label>
                <input
                  type="number"
                  step="100"
                  value={editQuantity}
                  onChange={(e) => {
                    const qty = Number(e.target.value);
                    setEditQuantity(qty);
                    const amt = editPrice * qty;
                    const comm = Math.max(feeSettings.minCommission, Number((amt * feeSettings.commissionRate).toFixed(2)));
                    const trans = Number((amt * feeSettings.transferFeeRate).toFixed(2));
                    const stamp = editingTrade.type === "SELL" ? Number((amt * feeSettings.stampDutyRate).toFixed(2)) : 0;
                    setEditCommission(comm);
                    setEditTransferFee(trans);
                    setEditStampDuty(stamp);
                  }}
                  className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs font-mono text-slate-200 mt-1 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {/* 编辑税费细分费用 */}
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-850 space-y-3">
              <span className="text-[10px] font-bold text-slate-400 uppercase block tracking-wider">
                手续费细目编辑 (已根据系统当前费率自动同步算好)
              </span>
              
              <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                <div>
                  <label className="text-[9px] text-slate-500 block">券商佣金 (元)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editCommission}
                    onChange={(e) => setEditCommission(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-[11px] text-slate-200 mt-1 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[9px] text-slate-500 block">印花税 (元)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editStampDuty}
                    disabled={editingTrade.type === "BUY"}
                    onChange={(e) => setEditStampDuty(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-[11px] text-slate-200 mt-1 disabled:opacity-50 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[9px] text-slate-500 block">过户费 (元)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editTransferFee}
                    onChange={(e) => setEditTransferFee(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-[11px] text-slate-200 mt-1 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-between border-t border-slate-900 pt-2 text-[11px] font-mono font-bold text-slate-300">
                <span>总交易费用计费同步 (自动加总):</span>
                <span className="text-cyan-400 font-mono">
                  {(Number(editCommission) + Number(editStampDuty) + Number(editTransferFee)).toFixed(2)} 元
                </span>
              </div>
            </div>

            {/* 编辑审计属性与违规标签 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-slate-500 block tracking-wider mb-1">纪律审计结论</label>
                <select
                  value={editRulesConclusion}
                  onChange={(e) => setEditRulesConclusion(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="符合规则">符合规则 (合规交易)</option>
                  <option value="违规交易">违规交易 (违纪操作)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 block tracking-wider mb-1">违纪标签 (逗号分隔)</label>
                <input
                  type="text"
                  value={editViolationTags.join(", ")}
                  onChange={(e) => setEditViolationTags(e.target.value.split(",").map(x => x.trim()).filter(Boolean))}
                  placeholder="无违纪 (或写未向上买入,偏离度过高等)"
                  className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {/* 反思原因 */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 block tracking-wider">交易因由决策反思 (纠错重点)</label>
              <textarea
                rows={2}
                value={editReason}
                onChange={(e) => setEditReason(e.target.value)}
                className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 leading-normal"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 block tracking-wider">流水备注</label>
              <input
                type="text"
                value={editRemark}
                onChange={(e) => setEditRemark(e.target.value)}
                className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <button
              onClick={handleUpdateTrade}
              className="w-full py-2 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white font-bold text-xs rounded transition shadow"
            >
              保存修改并实时重算持仓账目
            </button>

          </div>
        </div>
      )}

    </div>
  );
}
