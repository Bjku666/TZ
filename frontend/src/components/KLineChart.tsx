import { useEffect, useState, useRef } from "react";
import { KLinePoint } from "../types";
import { TrendingUp, AlertTriangle } from "lucide-react";

interface KLineChartProps {
  code: string;
  name: string;
  onClose?: () => void;
}

export default function KLineChart({ code, name }: KLineChartProps) {
  const [klines, setKlines] = useState<KLinePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    setError(null);
    setHoveredIndex(null);

    fetch(`/api/history/${code}`)
      .then(res => {
        if (!res.ok) throw new Error("获取K线失败");
        return res.json();
      })
      .then(data => {
        setKlines(data.klines || []);
      })
      .catch(err => {
        console.error(err);
        setError("无法加载历史K线数据");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [code]);

  if (loading) {
    return (
      <div className="flex h-72 items-center justify-center bg-slate-900 border border-slate-800 rounded-lg shadow-sm">
        <div className="text-center text-slate-400">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500 mx-auto mb-2"></div>
          <p className="text-xs">加载 K 线数据中...</p>
        </div>
      </div>
    );
  }

  if (error || klines.length === 0) {
    return (
      <div className="flex flex-col h-72 items-center justify-center bg-slate-900 border border-slate-800 rounded-lg p-4 text-center text-slate-400 shadow-sm">
        <AlertTriangle className="h-8 w-8 text-amber-500 mb-2" />
        <p className="text-sm font-medium text-slate-200">{error || "缺少历史K线数据"}</p>
        <p className="text-xs text-slate-500 mt-1">代码: {code} | 名称: {name}</p>
        <button
          onClick={() => {
            setLoading(true);
            fetch("/api/watchlist/fetch-history", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ code })
            })
              .then(() => fetch(`/api/history/${code}`))
              .then(res => res.json())
              .then(data => setKlines(data.klines || []))
              .catch(() => setError("下载历史数据失败"))
              .finally(() => setLoading(false));
          }}
          className="mt-4 px-3 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded transition shadow-sm"
        >
          立即下载历史 K 线
        </button>
      </div>
    );
  }

  // 渲染配置
  const svgWidth = 700;
  const klineSvgHeight = 200;
  const volSvgHeight = 60;
  const padding = { top: 15, right: 10, bottom: 15, left: 50 };

  // 坐标系范围计算
  const prices = klines.flatMap(k => [k.open, k.high, k.low, k.close, k.ma5 || 0, k.ma10 || 0, k.ma20 || 0].filter(p => p > 0));
  const maxPrice = Math.max(...prices) * 1.01;
  const minPrice = Math.min(...prices) * 0.99;

  const maxVol = Math.max(...klines.map(k => k.volume || 0));

  const count = klines.length;
  const slotWidth = (svgWidth - padding.left - padding.right) / count;
  const candleWidth = Math.max(2, slotWidth * 0.7);
  const clampIndex = (index: number) => Math.min(count - 1, Math.max(0, index));

  const getX = (index: number) => padding.left + index * slotWidth + slotWidth / 2;
  const getIndexBySvgX = (svgX: number) => {
    const rawIndex = Math.round((svgX - padding.left - slotWidth / 2) / slotWidth);
    return clampIndex(rawIndex);
  };
  const getY = (val: number) => {
    const ratio = (val - minPrice) / (maxPrice - minPrice);
    return klineSvgHeight - padding.bottom - ratio * (klineSvgHeight - padding.top - padding.bottom);
  };
  const getVolY = (val: number) => {
    if (maxVol === 0) return volSvgHeight - 5;
    const ratio = val / maxVol;
    return volSvgHeight - 5 - ratio * (volSvgHeight - 10);
  };

  // 生成 MA 路径的辅助方法
  const generateLinePath = (key: 'ma5' | 'ma10' | 'ma20') => {
    let started = false;
    return klines.reduce<string[]>((path, k, i) => {
      const val = k[key];
      if (typeof val !== "number" || !Number.isFinite(val) || val <= 0) {
        started = false;
        return path;
      }
      path.push(`${started ? "L" : "M"} ${getX(i)} ${getY(val)}`);
      started = true;
      return path;
    }, []).join(" ");
  };

  const ma5Path = generateLinePath('ma5');
  const ma10Path = generateLinePath('ma10');
  const ma20Path = generateLinePath('ma20');

  // 当前 hover 或最新的点
  const activeIndex = hoveredIndex === null ? count - 1 : clampIndex(hoveredIndex);
  const activePoint = klines[activeIndex];
  const previousPoint = activeIndex > 0 ? klines[activeIndex - 1] : null;
  const activeChangePct = activePoint && previousPoint
    ? ((activePoint.close - previousPoint.close) / previousPoint.close * 100)
    : 0;
  const formatLineValue = (value?: number) => (
    typeof value === "number" && Number.isFinite(value) && value > 0 ? value.toFixed(2) : "--"
  );
  const quoteMetrics = activePoint ? [
    {
      label: "价格",
      value: activePoint.close.toFixed(2),
      valueClassName: activePoint.close >= activePoint.open ? "text-rose-400" : "text-emerald-400"
    },
    {
      label: "涨跌幅",
      value: `${activeChangePct >= 0 ? "+" : ""}${activeChangePct.toFixed(2)}%`,
      valueClassName: activeChangePct >= 0 ? "text-rose-400" : "text-emerald-400"
    },
    { label: "开", value: activePoint.open.toFixed(2) },
    { label: "高", value: activePoint.high.toFixed(2) },
    { label: "低", value: activePoint.low.toFixed(2) },
    {
      label: "量",
      value: `${(activePoint.volume / 10000).toLocaleString("zh-CN", { maximumFractionDigits: 1 })}万手`
    }
  ] : [];
  const maMetrics = [
    { label: "MA5", value: formatLineValue(activePoint?.ma5), className: "text-amber-400", swatchClassName: "bg-amber-500" },
    { label: "MA10", value: formatLineValue(activePoint?.ma10), className: "text-cyan-300", swatchClassName: "bg-cyan-400" },
    { label: "MA20", value: formatLineValue(activePoint?.ma20), className: "text-pink-400", swatchClassName: "bg-pink-500" }
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 font-sans select-none text-slate-200 shadow-sm">
      {/* 头部信息 */}
      <div className="border-b border-slate-800 pb-3 mb-3 space-y-2 overflow-hidden">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="shrink-0 whitespace-nowrap text-base font-bold text-slate-100">{name}</span>
          <span className="shrink-0 whitespace-nowrap rounded border border-slate-800 bg-slate-950/70 px-2 py-0.5 font-mono text-xs text-slate-400">{code}</span>
        </div>
        {activePoint && (
          <dl
            className="grid min-w-0 gap-x-3 gap-y-1.5 font-mono text-xs text-slate-400"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(7.5rem, 1fr))" }}
          >
            {quoteMetrics.map(metric => (
              <div key={metric.label} className="flex min-w-0 items-baseline gap-1">
                <dt className="shrink-0 text-slate-500">{metric.label}:</dt>
                <dd className={`min-w-0 truncate font-semibold ${metric.valueClassName || "text-slate-300"}`}>
                  {metric.value}
                </dd>
              </div>
            ))}
          </dl>
        )}
        <div
          className="grid min-w-0 gap-x-3 gap-y-1.5 font-mono text-xs text-slate-500"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(6.5rem, 1fr))" }}
        >
          {maMetrics.map(metric => (
            <span key={metric.label} className={`flex min-w-0 items-center gap-1 ${metric.className}`}>
              <span className={`h-0.5 w-2.5 shrink-0 ${metric.swatchClassName}`}></span>
              <span className="shrink-0">{metric.label}:</span>
              <span className="min-w-0 truncate">{metric.value}</span>
            </span>
          ))}
        </div>
      </div>

      {/* SVG K 线主图与交易量 */}
      <div 
        ref={chartRef}
        className="relative overflow-hidden cursor-crosshair"
        onMouseLeave={() => setHoveredIndex(null)}
        onMouseMove={(e) => {
          if (!chartRef.current || klines.length === 0) return;
          const rect = chartRef.current.getBoundingClientRect();
          if (rect.width === 0) return;
          const svgX = ((e.clientX - rect.left) / rect.width) * svgWidth;
          setHoveredIndex(getIndexBySvgX(svgX));
        }}
      >
        {/* K线主图 */}
        <svg viewBox={`0 0 ${svgWidth} ${klineSvgHeight}`} className="w-full h-auto">
          {/* 背景网格线 */}
          <line x1={padding.left} y1={getY(minPrice)} x2={svgWidth - padding.right} y2={getY(minPrice)} stroke="#2b2b2b" strokeDasharray="2,2" />
          <line x1={padding.left} y1={getY((maxPrice + minPrice) / 2)} x2={svgWidth - padding.right} y2={getY((maxPrice + minPrice) / 2)} stroke="#2b2b2b" strokeDasharray="2,2" />
          <line x1={padding.left} y1={getY(maxPrice)} x2={svgWidth - padding.right} y2={getY(maxPrice)} stroke="#2b2b2b" strokeDasharray="2,2" />

          {/* 价格 Y 轴刻度 */}
          <text x={padding.left - 8} y={getY(maxPrice) + 4} textAnchor="end" className="text-[10px] font-mono fill-slate-400">{maxPrice.toFixed(2)}</text>
          <text x={padding.left - 8} y={getY((maxPrice + minPrice) / 2) + 4} textAnchor="end" className="text-[10px] font-mono fill-slate-400">{((maxPrice + minPrice) / 2).toFixed(2)}</text>
          <text x={padding.left - 8} y={getY(minPrice) + 4} textAnchor="end" className="text-[10px] font-mono fill-slate-400">{minPrice.toFixed(2)}</text>

          {/* 蜡烛图蜡烛实体和影线 */}
          {klines.map((k, i) => {
            const isUp = k.close >= k.open;
            const colorClass = isUp ? "#e11d48" : "#059669"; // 玫瑰红 (涨) vs 翡翠绿 (跌)
            const x = getX(i);
            const yOpen = getY(k.open);
            const yClose = getY(k.close);
            const yHigh = getY(k.high);
            const yLow = getY(k.low);

            return (
              <g key={i}>
                {/* 影线 */}
                <line x1={x} y1={yHigh} x2={x} y2={yLow} stroke={colorClass} strokeWidth={1} />
                {/* 实体 */}
                <rect
                  x={x - candleWidth / 2}
                  y={Math.min(yOpen, yClose)}
                  width={candleWidth}
                  height={Math.max(1.5, Math.abs(yOpen - yClose))}
                  fill={isUp ? "none" : colorClass}
                  stroke={colorClass}
                  strokeWidth={1.2}
                />
              </g>
            );
          })}

          {/* 均线曲线 */}
          {ma5Path && <path d={ma5Path} fill="none" stroke="#d97706" strokeWidth={1.5} />}
          {ma10Path && <path d={ma10Path} fill="none" stroke="#0891b2" strokeWidth={1.5} />}
          {ma20Path && <path d={ma20Path} fill="none" stroke="#db2777" strokeWidth={1.5} />}

          {/* Hover 十字竖线 */}
          {hoveredIndex !== null && (
            <line
              x1={getX(activeIndex)}
              y1={padding.top}
              x2={getX(activeIndex)}
              y2={klineSvgHeight - padding.bottom}
              stroke="#94a3b8"
              strokeWidth={0.8}
              strokeDasharray="3,3"
            />
          )}
        </svg>

        {/* 交易量主图 */}
        <div className="border-t border-slate-800 my-1"></div>
        <svg viewBox={`0 0 ${svgWidth} ${volSvgHeight}`} className="w-full h-auto">
          {/* 量柱子 */}
          {klines.map((k, i) => {
            const isUp = k.close >= k.open;
            const colorClass = isUp ? "#e11d48" : "#059669";
            const x = getX(i);
            const yVol = getVolY(k.volume);

            return (
              <rect
                key={i}
                x={x - candleWidth / 2}
                y={yVol}
                width={candleWidth}
                height={volSvgHeight - 5 - yVol}
                fill={isUp ? "none" : colorClass}
                stroke={colorClass}
                strokeWidth={1}
              />
            );
          })}

          {/* 日期 X 轴标签 */}
          {klines.map((k, i) => {
            // 只显示首尾及中间等间隔日期
            const showLabel = i === 0 || i === Math.floor(count / 2) || i === count - 1;
            if (!showLabel) return null;
            return (
              <text
                key={i}
                x={getX(i)}
                y={volSvgHeight - 2}
                textAnchor="middle"
                className="text-[9px] font-mono fill-slate-400"
              >
                {k.date.substring(5)}
              </text>
            );
          })}

          {/* Hover 十字竖线 */}
          {hoveredIndex !== null && (
            <line
              x1={getX(activeIndex)}
              y1={0}
              x2={getX(activeIndex)}
              y2={volSvgHeight - 15}
              stroke="#94a3b8"
              strokeWidth={0.8}
              strokeDasharray="3,3"
            />
          )}
        </svg>
      </div>

      <div className="mt-2 text-center text-[10px] text-slate-500 flex justify-center items-center space-x-1 font-mono">
        <TrendingUp className="h-3 w-3 text-rose-400" />
        <span>支持鼠标悬停移动查看每根日K线细节与偏离指标。5日均线回踩区间在0%~2%最优。</span>
      </div>
    </div>
  );
}
