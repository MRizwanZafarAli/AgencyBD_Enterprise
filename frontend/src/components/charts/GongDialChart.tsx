import type { FC } from 'react';
import { Mic, Headphones, CheckCircle2 } from 'lucide-react';

interface GongDialChartProps {
  repPct: number;       // e.g. 38 or 43
  prospectPct: number;  // e.g. 62 or 57
  questionsCount?: number;
}

export const GongDialChart: FC<GongDialChartProps> = ({
  repPct = 43,
  prospectPct = 57,
  questionsCount = 12
}) => {
  // Benchmark standard: Rep <= 43%, Prospect >= 57%
  const isOptimal = repPct <= 45;

  // Donut arc calculation
  const size = 160;
  const strokeWidth = 14;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const repStrokeDash = (repPct / 100) * circumference;
  const prospectStrokeDash = (prospectPct / 100) * circumference;

  return (
    <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-white">Gong Golden Talk-to-Listen Ratio</span>
          <p className="text-[11px] text-slate-400">Industry benchmark: 43% Rep / 57% Prospect</p>
        </div>
        <span
          className={`px-2 py-0.5 rounded-full text-[10px] font-mono border flex items-center space-x-1 ${
            isOptimal
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
          }`}
        >
          <CheckCircle2 className="h-3 w-3" />
          <span>{isOptimal ? 'GOLDEN RATIO' : 'REP TALKING TOO MUCH'}</span>
        </span>
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-around gap-4 pt-2">
        {/* Circular Dial SVG */}
        <div className="relative flex items-center justify-center">
          <svg width={size} height={size} className="transform -rotate-90">
            {/* Background Circle */}
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              stroke="rgba(255, 255, 255, 0.08)"
              strokeWidth={strokeWidth}
              fill="transparent"
            />
            {/* Prospect Arc (Cyan/Emerald) */}
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              stroke="#0b5f58"
              strokeWidth={strokeWidth}
              fill="transparent"
              strokeDasharray={`${prospectStrokeDash} ${circumference}`}
              strokeDashoffset={-repStrokeDash}
              strokeLinecap="round"
              className="transition-all duration-700"
            />
            {/* Rep Arc (Indigo) */}
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              stroke="#14b8a6"
              strokeWidth={strokeWidth}
              fill="transparent"
              strokeDasharray={`${repStrokeDash} ${circumference}`}
              strokeLinecap="round"
              className="transition-all duration-700"
            />
          </svg>

          {/* Center Metrics */}
          <div className="absolute flex flex-col items-center justify-center text-center">
            <span className="text-xs font-mono text-slate-400">Prospect</span>
            <span className="text-2xl font-bold font-mono text-white">{prospectPct}%</span>
            <span className="text-[10px] font-mono text-indigo-400">Rep {repPct}%</span>
          </div>
        </div>

        {/* Legend & Breakdown Card */}
        <div className="space-y-3 text-xs w-full sm:w-auto">
          <div className="flex items-center justify-between sm:justify-start sm:space-x-4 p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
            <div className="flex items-center space-x-2">
              <Headphones className="h-4 w-4 text-cyan-400" />
              <span className="text-slate-300">Prospect Talking</span>
            </div>
            <span className="font-mono font-bold text-cyan-400">{prospectPct}% (Listening)</span>
          </div>

          <div className="flex items-center justify-between sm:justify-start sm:space-x-4 p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
            <div className="flex items-center space-x-2">
              <Mic className="h-4 w-4 text-indigo-400" />
              <span className="text-slate-300">Sales Rep Pitching</span>
            </div>
            <span className="font-mono font-bold text-indigo-400">{repPct}% (Speaking)</span>
          </div>

          <div className="p-2 rounded-lg bg-slate-950/40 border border-slate-850 text-[11px] font-mono flex items-center justify-between">
            <span className="text-slate-400">Discovery Questions Asked:</span>
            <span className="text-emerald-400 font-bold">{questionsCount} / 14 Benchmark</span>
          </div>
        </div>
      </div>
    </div>
  );
};
