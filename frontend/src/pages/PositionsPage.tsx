import { EmptyState, SectionTitle } from "../components/common/Primitives";
import { PositionCard } from "../components/position/PositionCard";
import type { Position } from "../types";

export function PositionsPage({
  positions,
  onSell,
  onDefer,
}: {
  positions: Position[];
  onSell: (position: Position) => void;
  onDefer: (position: Position) => void;
}) {
  return (
    <div className="space-y-4">
      <SectionTitle title="持仓监控" subtitle="持仓建议只围绕当前后端隔日卖出状态、T+1和可执行性展示。" />
      {positions.length === 0 ? (
        <EmptyState title="暂无持仓" detail="买入交易保存后，后端会重新计算持仓与资产。" />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {positions.map(position => (
            <div key={`${position.code}_${position.buyDate}`}>
              <PositionCard position={position} onSell={onSell} onDefer={onDefer} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
