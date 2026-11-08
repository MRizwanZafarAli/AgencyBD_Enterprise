import type { FC } from 'react';
import { Sparkles } from 'lucide-react';

interface LavenderRadarProps {
  score: number; // overall 0-100
  readabilityScore?: number; // 0-100
  lengthScore?: number;      // 0-100
  spamSafetyScore?: number;  // 0-100
  ctaFrictionScore?: number; // 0-100
  subjectHookScore?: number; // 0-100
}

export const LavenderRadarChart: FC<LavenderRadarProps> = ({
  score = 92,
  readabilityScore = 95,
  lengthScore = 90,
  spamSafetyScore = 100,
  ctaFrictionScore = 94,
  subjectHookScore = 88
}) => {
  // 5 axes coordinates on a pentagon
  const size = 200;
  const center = size / 2;
  const radius = 70;

  const axes = [
    { label: 'Readability', val: readabilityScore, angle: -90 },
    { label: 'Word Count', val: lengthScore, angle: -18 },
    { label: 'Spam Safety', val: spamSafetyScore, angle: 54 },
    { label: 'CTA Friction', val: ctaFrictionScore, angle: 126 },
    { label: 'Subject Hook', val: subjectHookScore, angle: 198 }
  ];

  const getCoord = (angleDeg: number, r: number) => {
    const rad = (angleDeg * Math.PI) / 180;
    return {
      x: center + r * Math.cos(rad),
      y: center + r * Math.sin(rad)
    };
  };

  // Background concentric pentagon rings
  const ringLevels = [0.25, 0.5, 0.75, 1.0];

  // Polygon points for active scores
  const scorePoints = axes.map((axis) => {
    const r = (axis.val / 100) * radius;
    const pt = getCoord(axis.angle, r);
    return `${pt.x},${pt.y}`;
  }).join(' ');

  return (
    <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-white">Lavender 5-Axis Email Deliverability Radar</span>
          <p className="text-[11px] text-slate-400">Heuristic audit based on 100M+ high-converting outbound emails</p>
        </div>
        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-mono font-bold">
          <Sparkles className="h-3.5 w-3.5 text-purple-400" />
          <span>SCORE: {score}/100</span>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-around gap-2">
        {/* SVG Pentagon Radar */}
        <div className="relative">
          <svg width={size} height={size} className="overflow-visible select-none">
            <defs>
              <linearGradient id="radarGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#14b8a6" stopOpacity="0.45" />
                <stop offset="100%" stopColor="#b07a00" stopOpacity="0.15" />
              </linearGradient>
            </defs>

            {/* Background concentric rings */}
            {ringLevels.map((lvl) => {
              const r = lvl * radius;
              const pts = axes.map((a) => {
                const pt = getCoord(a.angle, r);
                return `${pt.x},${pt.y}`;
              }).join(' ');
              return (
                <polygon
                  key={lvl}
                  points={pts}
                  fill="none"
                  stroke="rgba(255,255,255,0.07)"
                  strokeWidth="1"
                />
              );
            })}

            {/* Axis spokes from center */}
            {axes.map((a) => {
              const pt = getCoord(a.angle, radius);
              return (
                <line
                  key={a.label}
                  x1={center}
                  y1={center}
                  x2={pt.x}
                  y2={pt.y}
                  stroke="rgba(255,255,255,0.1)"
                  strokeWidth="1"
                  strokeDasharray="2 2"
                />
              );
            })}

            {/* Filled Active Score Polygon */}
            <polygon
              points={scorePoints}
              fill="url(#radarGrad)"
              stroke="#14b8a6"
              strokeWidth="2"
              className="transition-all duration-500"
            />

            {/* Vertices & Axis Labels */}
            {axes.map((a) => {
              const r = (a.val / 100) * radius;
              const pt = getCoord(a.angle, r);
              const labelPt = getCoord(a.angle, radius + 15);

              return (
                <g key={a.label}>
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r="3.5"
                    fill="#14b8a6"
                    stroke="#ffffff"
                    strokeWidth="1.5"
                  />
                  <text
                    x={labelPt.x}
                    y={labelPt.y}
                    fill="#94a3b8"
                    fontSize="9"
                    fontFamily="sans-serif"
                    textAnchor="middle"
                    alignmentBaseline="middle"
                  >
                    {a.label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Breakdown Indicators */}
        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono w-full sm:w-auto">
          <div className="p-2 rounded bg-slate-950/60 border border-slate-800 flex justify-between items-center space-x-2">
            <span className="text-slate-400">Readability:</span>
            <span className="text-emerald-400 font-bold">{readabilityScore}%</span>
          </div>
          <div className="p-2 rounded bg-slate-950/60 border border-slate-800 flex justify-between items-center space-x-2">
            <span className="text-slate-400">Word Count:</span>
            <span className="text-emerald-400 font-bold">{lengthScore}%</span>
          </div>
          <div className="p-2 rounded bg-slate-950/60 border border-slate-800 flex justify-between items-center space-x-2">
            <span className="text-slate-400">Spam Shield:</span>
            <span className="text-emerald-400 font-bold">{spamSafetyScore}%</span>
          </div>
          <div className="p-2 rounded bg-slate-950/60 border border-slate-800 flex justify-between items-center space-x-2">
            <span className="text-slate-400">Low-Friction CTA:</span>
            <span className="text-emerald-400 font-bold">{ctaFrictionScore}%</span>
          </div>
          <div className="p-2 rounded bg-slate-950/60 border border-slate-800 col-span-2 flex justify-between items-center">
            <span className="text-slate-400">Executive Subject Hook:</span>
            <span className="text-purple-400 font-bold">{subjectHookScore}%</span>
          </div>
        </div>
      </div>
    </div>
  );
};
