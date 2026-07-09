/**
 * Premium SVG chart components — zero dependencies, pure React + SVG.
 * Designed for the AntCobranzas business intelligence dashboard.
 */

// ════════════════════════════════════════════════════════════════
// DONUT CHART — Modern ring chart with center metric
// ════════════════════════════════════════════════════════════════
export function DonutChart({ slices, size = 200, thickness = 32, centerLabel, centerValue, centerSub }) {
  const cx = size / 2, cy = size / 2;
  const outerR = size / 2 - 8;
  const innerR = outerR - thickness;
  const total = slices.reduce((a, b) => a + b.value, 0) || 1;
  let cumAngle = -90;

  const arcs = slices.filter(s => s.value > 0).map((s) => {
    const angle = (s.value / total) * 360;
    const startRad = (cumAngle * Math.PI) / 180;
    const endRad = ((cumAngle + angle) * Math.PI) / 180;
    cumAngle += angle;
    const large = angle > 180 ? 1 : 0;

    if (angle >= 359.99) {
      return (
        <g key={s.label}>
          <circle cx={cx} cy={cy} r={outerR} fill={s.color} />
          <circle cx={cx} cy={cy} r={innerR} fill="white" />
        </g>
      );
    }

    const ox1 = cx + outerR * Math.cos(startRad), oy1 = cy + outerR * Math.sin(startRad);
    const ox2 = cx + outerR * Math.cos(endRad),   oy2 = cy + outerR * Math.sin(endRad);
    const ix1 = cx + innerR * Math.cos(endRad),    iy1 = cy + innerR * Math.sin(endRad);
    const ix2 = cx + innerR * Math.cos(startRad),  iy2 = cy + innerR * Math.sin(startRad);

    return (
      <path
        key={s.label}
        d={`M ${ox1} ${oy1}
            A ${outerR} ${outerR} 0 ${large} 1 ${ox2} ${oy2}
            L ${ix1} ${iy1}
            A ${innerR} ${innerR} 0 ${large} 0 ${ix2} ${iy2} Z`}
        fill={s.color}
        stroke="white"
        strokeWidth="2"
      />
    );
  });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {arcs}
      {centerValue !== undefined && (
        <g>
          {centerLabel && (
            <text x={cx} y={cy - 16} textAnchor="middle" className="fill-gray-400" fontSize="11" fontWeight="600">
              {centerLabel}
            </text>
          )}
          <text x={cx} y={cy + 8} textAnchor="middle" className="fill-gray-900" fontSize="26" fontWeight="800">
            {centerValue}
          </text>
          {centerSub && (
            <text x={cx} y={cy + 26} textAnchor="middle" className="fill-gray-400" fontSize="10" fontWeight="500">
              {centerSub}
            </text>
          )}
        </g>
      )}
    </svg>
  );
}

// ════════════════════════════════════════════════════════════════
// GAUGE — Semi-circular speedometer with animated fill
// ════════════════════════════════════════════════════════════════
export function GaugeChart({ value, max = 100, label, size = 180, color = '#6366F1', zones }) {
  const cx = size / 2, cy = size / 2 + 10;
  const r = size / 2 - 16;
  const pct = Math.min(value / max, 1);
  const startAngle = -180;
  const sweep = 180;

  // Background arc
  const bgStart = ((startAngle) * Math.PI) / 180;
  const bgEnd = ((startAngle + sweep) * Math.PI) / 180;
  const bgX1 = cx + r * Math.cos(bgStart), bgY1 = cy + r * Math.sin(bgStart);
  const bgX2 = cx + r * Math.cos(bgEnd),   bgY2 = cy + r * Math.sin(bgEnd);

  // Value arc
  const valAngle = startAngle + sweep * pct;
  const valRad = (valAngle * Math.PI) / 180;
  const vx = cx + r * Math.cos(valRad), vy = cy + r * Math.sin(valRad);
  const largeArc = (sweep * pct) > 180 ? 1 : 0;

  // Zone arcs (colored sections if provided)
  const zoneArcs = (zones || []).map((zone, i) => {
    const zStart = startAngle + sweep * (zone.from / max);
    const zEnd = startAngle + sweep * (zone.to / max);
    const zSweep = zEnd - zStart;
    const zStartRad = (zStart * Math.PI) / 180;
    const zEndRad = (zEnd * Math.PI) / 180;
    const zx1 = cx + r * Math.cos(zStartRad), zy1 = cy + r * Math.sin(zStartRad);
    const zx2 = cx + r * Math.cos(zEndRad),   zy2 = cy + r * Math.sin(zEndRad);
    return (
      <path key={i}
        d={`M ${zx1} ${zy1} A ${r} ${r} 0 ${zSweep > 180 ? 1 : 0} 1 ${zx2} ${zy2}`}
        fill="none" stroke={zone.color} strokeWidth="8" strokeLinecap="round" opacity="0.25"
      />
    );
  });

  return (
    <svg width={size} height={size * 0.65} viewBox={`0 0 ${size} ${size * 0.65}`}>
      {/* Background */}
      <path
        d={`M ${bgX1} ${bgY1} A ${r} ${r} 0 0 1 ${bgX2} ${bgY2}`}
        fill="none" stroke="#E2E8F0" strokeWidth="12" strokeLinecap="round"
      />
      {zoneArcs}
      {/* Value */}
      {pct > 0.005 && (
        <path
          d={`M ${bgX1} ${bgY1} A ${r} ${r} 0 ${largeArc} 1 ${vx} ${vy}`}
          fill="none" stroke={color} strokeWidth="12" strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
      )}
      {/* Needle dot */}
      <circle cx={vx} cy={vy} r="6" fill={color} stroke="white" strokeWidth="3" />
      {/* Center text */}
      <text x={cx} y={cy - 6} textAnchor="middle" className="fill-gray-900" fontSize="28" fontWeight="800">
        {typeof value === 'number' ? Math.round(value) : value}
      </text>
      {label && (
        <text x={cx} y={cy + 12} textAnchor="middle" className="fill-gray-400" fontSize="10" fontWeight="600">
          {label}
        </text>
      )}
    </svg>
  );
}

// ════════════════════════════════════════════════════════════════
// STACKED BAR — Horizontal bars with multiple segments
// ════════════════════════════════════════════════════════════════
export function StackedBar({ label, segments, total, height = 28 }) {
  let offset = 0;
  const barWidth = 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className="text-xs font-semibold text-gray-500">{total} clientes</span>
      </div>
      <svg width="100%" height={height} viewBox={`0 0 ${barWidth} ${height}`} preserveAspectRatio="none">
        <rect x="0" y="0" width={barWidth} height={height} rx="4" fill="#F1F5F9" />
        {segments.filter(s => s.value > 0).map((s, i) => {
          const w = total > 0 ? (s.value / total) * barWidth : 0;
          const x = offset;
          offset += w;
          return (
            <rect key={i} x={x} y="0" width={w} height={height} fill={s.color}
              rx={i === 0 ? 4 : 0} />
          );
        })}
      </svg>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
// VERTICAL BAR CHART — Classic column chart
// ════════════════════════════════════════════════════════════════
export function BarChartVertical({ bars, height = 200, barColor = '#6366F1', showValues = true }) {
  const maxVal = Math.max(...bars.map(b => b.value), 1);
  const barW = Math.min(40, Math.max(16, 300 / bars.length));
  const gap = Math.max(4, barW * 0.4);
  const totalW = bars.length * (barW + gap);
  const padTop = 24, padBottom = 50;

  return (
    <svg width="100%" height={height + padBottom} viewBox={`0 0 ${totalW} ${height + padBottom}`}
      preserveAspectRatio="xMidYMax meet" className="overflow-visible">
      {/* Grid lines */}
      {[0.25, 0.5, 0.75, 1].map(p => (
        <line key={p}
          x1="0" y1={padTop + (1 - p) * (height - padTop)} x2={totalW} y2={padTop + (1 - p) * (height - padTop)}
          stroke="#F1F5F9" strokeWidth="1"
        />
      ))}
      {bars.map((b, i) => {
        const barH = (b.value / maxVal) * (height - padTop);
        const x = i * (barW + gap) + gap / 2;
        const y = height - barH;
        const fill = b.color || barColor;
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={barH} rx="4" fill={fill} opacity="0.85" />
            {showValues && (
              <text x={x + barW / 2} y={y - 6} textAnchor="middle" fontSize="9" fontWeight="700" className="fill-gray-600">
                {b.value}
              </text>
            )}
            <text x={x + barW / 2} y={height + 14} textAnchor="middle" fontSize="8" className="fill-gray-500"
              transform={`rotate(-30 ${x + barW / 2} ${height + 14})`}>
              {b.label.length > 10 ? b.label.slice(0, 10) + '…' : b.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ════════════════════════════════════════════════════════════════
// TREEMAP — Rectangle-based proportional visualization
// ════════════════════════════════════════════════════════════════
export function TreeMap({ items, width = 600, height = 260, colorScale }) {
  if (!items.length) return null;
  const total = items.reduce((a, b) => a + b.value, 0) || 1;
  const sorted = [...items].sort((a, b) => b.value - a.value);

  // Simple squarified-ish layout: row-based packing
  const rects = [];
  let x = 0, y = 0, rowH = height;
  let remaining = [...sorted];
  let areaLeft = width * height;
  let yOffset = 0;

  while (remaining.length > 0) {
    // Take items for this row
    const rowItems = [];
    const rowArea = remaining.reduce((s, r) => s + r.value, 0);
    let rowFraction = 0;
    const isVertical = (width - x) < (height - yOffset);

    // Simple: fill rows left to right
    const rowWidth = width;
    let cumFrac = 0;
    for (const item of remaining) {
      rowItems.push(item);
      cumFrac += item.value / total;
      if (cumFrac >= 0.3 && rowItems.length >= 2) break;
    }
    remaining = remaining.slice(rowItems.length);

    const rowTotal = rowItems.reduce((s, r) => s + r.value, 0);
    const thisRowH = (rowTotal / total) * height;

    let xOff = 0;
    rowItems.forEach((item, idx) => {
      const w = rowTotal > 0 ? (item.value / rowTotal) * width : 0;
      const c = colorScale ? colorScale(idx, item) : item.color || `hsl(${idx * 47}, 65%, 55%)`;
      rects.push({
        x: xOff, y: yOffset, w, h: thisRowH,
        label: item.label, value: item.value, color: c,
        pct: Math.round((item.value / total) * 100),
      });
      xOff += w;
    });
    yOffset += thisRowH;
  }

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      {rects.map((r, i) => (
        <g key={i}>
          <rect x={r.x} y={r.y} width={r.w} height={r.h} fill={r.color} stroke="white" strokeWidth="2" rx="4" />
          {r.w > 50 && r.h > 30 && (
            <>
              <text x={r.x + r.w / 2} y={r.y + r.h / 2 - 4} textAnchor="middle"
                fontSize={r.w > 100 ? 11 : 9} fontWeight="700" fill="white" opacity="0.95">
                {r.label.length > 14 ? r.label.slice(0, 14) + '…' : r.label}
              </text>
              <text x={r.x + r.w / 2} y={r.y + r.h / 2 + 12} textAnchor="middle"
                fontSize={r.w > 100 ? 10 : 8} fontWeight="600" fill="white" opacity="0.75">
                {r.pct}% · {r.value}
              </text>
            </>
          )}
        </g>
      ))}
    </svg>
  );
}

// ════════════════════════════════════════════════════════════════
// FUNNEL CHART — Conversion funnel with decreasing widths
// ════════════════════════════════════════════════════════════════
export function FunnelChart({ stages, height = 220 }) {
  const maxVal = stages[0]?.value || 1;
  const stageH = height / stages.length;
  const maxW = 400;
  const minW = 80;

  return (
    <svg width="100%" viewBox={`0 0 ${maxW + 40} ${height + 10}`} preserveAspectRatio="xMidYMid meet">
      {stages.map((s, i) => {
        const w = maxVal > 0 ? Math.max(minW, (s.value / maxVal) * maxW) : minW;
        const nextW = i < stages.length - 1
          ? Math.max(minW, (stages[i + 1].value / maxVal) * maxW)
          : w * 0.8;
        const x = (maxW + 40 - w) / 2;
        const nextX = (maxW + 40 - nextW) / 2;
        const y = i * stageH;
        const pct = i > 0 ? Math.round((s.value / stages[0].value) * 100) : 100;

        return (
          <g key={i}>
            <path
              d={`M ${x} ${y}
                  L ${x + w} ${y}
                  L ${nextX + nextW} ${y + stageH}
                  L ${nextX} ${y + stageH} Z`}
              fill={s.color} opacity="0.85"
            />
            <text x={(maxW + 40) / 2} y={y + stageH / 2 - 2} textAnchor="middle"
              fontSize="12" fontWeight="700" fill="white">
              {s.label}
            </text>
            <text x={(maxW + 40) / 2} y={y + stageH / 2 + 14} textAnchor="middle"
              fontSize="10" fontWeight="600" fill="white" opacity="0.8">
              {s.value.toLocaleString()} ({pct}%)
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ════════════════════════════════════════════════════════════════
// MINI SPARKLINE — Inline trend indicator
// ════════════════════════════════════════════════════════════════
export function Sparkline({ data, width = 80, height = 24, color = '#6366F1' }) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data), min = Math.min(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={width} cy={parseFloat(points.split(' ').pop().split(',')[1])} r="2" fill={color} />
    </svg>
  );
}

// ════════════════════════════════════════════════════════════════
// SHARED LEGEND — Color legend strip
// ════════════════════════════════════════════════════════════════
export function Legend({ items }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: item.color }} />
          <span className="text-xs text-gray-500 font-medium">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
// KPI CARD — Enhanced metric card with optional trend
// ════════════════════════════════════════════════════════════════
const KPI_COLORS = {
  indigo:  { bg: 'bg-indigo-50',  icon: 'text-indigo-500',  ring: 'ring-indigo-100' },
  emerald: { bg: 'bg-emerald-50', icon: 'text-emerald-500', ring: 'ring-emerald-100' },
  rose:    { bg: 'bg-rose-50',    icon: 'text-rose-500',    ring: 'ring-rose-100' },
  violet:  { bg: 'bg-violet-50',  icon: 'text-violet-500',  ring: 'ring-violet-100' },
  amber:   { bg: 'bg-amber-50',   icon: 'text-amber-500',   ring: 'ring-amber-100' },
  teal:    { bg: 'bg-teal-50',    icon: 'text-teal-500',    ring: 'ring-teal-100' },
  blue:    { bg: 'bg-blue-50',    icon: 'text-blue-500',    ring: 'ring-blue-100' },
  green:   { bg: 'bg-green-50',   icon: 'text-green-500',   ring: 'ring-green-100' },
  purple:  { bg: 'bg-purple-50',  icon: 'text-purple-500',  ring: 'ring-purple-100' },
};

export function KPICard({ icon, label, value, sub, color = 'indigo', small, trend }) {
  const c = KPI_COLORS[color] || KPI_COLORS.indigo;
  return (
    <div className={`bg-white border border-slate-200 rounded-xl p-4 shadow-sm ring-1 ${c.ring}`}>
      <div className="flex items-center justify-between mb-2">
        <div className={`w-9 h-9 rounded-lg ${c.bg} flex items-center justify-center ${c.icon}`}>
          {icon}
        </div>
        {trend && <Sparkline data={trend} color={c.icon.includes('emerald') ? '#10B981' : '#6366F1'} />}
      </div>
      <p className={`${small ? 'text-lg' : 'text-2xl'} font-bold text-gray-900 leading-tight`}>{value}</p>
      <p className="text-xs text-gray-500 mt-0.5 font-medium">{label}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}
