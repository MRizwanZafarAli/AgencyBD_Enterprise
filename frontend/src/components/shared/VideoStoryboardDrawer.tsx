import { useState } from 'react';
import type { FC } from 'react';
import { Check, Copy, Film, Sparkles, Video, Clock } from 'lucide-react';
import { Badge, Button, Drawer } from '../ui';

export interface VideoStoryboardScene {
  scene_number: number;
  duration_seconds: number;
  camera_shot: string;
  visual_overlay: string;
  audio_script: string;
  animation_trigger: string;
}

export interface VideoStoryboardData {
  prospect_name: string;
  company_name: string;
  target_domain: string;
  total_runtime_seconds: number;
  storyboard_scenes: VideoStoryboardScene[];
  claims_included: {
    measured_lcp: boolean;
    missing_headers: boolean;
    portfolio_proof: boolean;
  };
  note: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  storyboard: VideoStoryboardData | null;
}

export const VideoStoryboardDrawer: FC<Props> = ({ open, onClose, storyboard }) => {
  const [copied, setCopied] = useState(false);

  if (!storyboard) return null;

  const copyFullScript = async () => {
    const text = storyboard.storyboard_scenes
      .map((s) => `[Scene ${s.scene_number} - ${s.duration_seconds}s | ${s.camera_shot}]\nVisual: ${s.visual_overlay}\nAudio: "${s.audio_script}"`)
      .join('\n\n');
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Drawer open={open} title={`Video Pitch Storyboard: ${storyboard.company_name}`} onClose={onClose} wide>
      <div className="space-y-4 text-xs">
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl border border-purple-500/30 bg-purple-500/5">
          <div className="flex items-center gap-2">
            <Video className="h-5 w-5 text-purple-400" />
            <div>
              <div className="font-semibold text-white text-sm">
                Target: {storyboard.target_domain} ({storyboard.prospect_name})
              </div>
              <div className="text-slate-400 flex items-center gap-2 mt-0.5">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" /> {storyboard.total_runtime_seconds}s estimated runtime
                </span>
                <span>·</span>
                <span className="text-purple-300">100% Evidence-Grounded</span>
              </div>
            </div>
          </div>
          <Button small variant="primary" onClick={copyFullScript}>
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied script' : 'Copy narration script'}
          </Button>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {storyboard.claims_included.measured_lcp && <Badge tone="good">Measured LCP Included</Badge>}
          {storyboard.claims_included.missing_headers && <Badge tone="warn">Security Header Gaps</Badge>}
          {storyboard.claims_included.portfolio_proof && <Badge tone="accent">Grounded Case Study Proof</Badge>}
        </div>

        <div className="space-y-3 mt-2">
          {storyboard.storyboard_scenes.map((s) => (
            <div
              key={s.scene_number}
              className="p-3.5 rounded-xl border border-white/5 bg-slate-900/60 space-y-2"
            >
              <div className="flex items-center justify-between gap-2 border-b border-white/5 pb-2">
                <div className="flex items-center gap-2">
                  <span className="h-5 w-5 rounded-full bg-purple-500/20 text-purple-300 font-semibold flex items-center justify-center text-[10px] tabular">
                    {s.scene_number}
                  </span>
                  <span className="font-medium text-slate-200">
                    {s.camera_shot}
                  </span>
                </div>
                <span className="text-slate-400 font-mono text-[11px]">
                  {s.duration_seconds}s
                </span>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                <div className="p-2.5 rounded-lg bg-black/40 border border-white/5">
                  <div className="text-[10px] uppercase font-semibold text-slate-500 flex items-center gap-1">
                    <Film className="h-3 w-3 text-indigo-400" /> Visual & Screen Cue
                  </div>
                  <div className="text-slate-300 mt-1">{s.visual_overlay}</div>
                  <div className="text-[10px] text-slate-500 mt-1">Trigger: {s.animation_trigger}</div>
                </div>

                <div className="p-2.5 rounded-lg bg-black/40 border border-purple-500/10">
                  <div className="text-[10px] uppercase font-semibold text-purple-400 flex items-center gap-1">
                    <Sparkles className="h-3 w-3" /> Narration (Verbal Script)
                  </div>
                  <div className="text-slate-200 mt-1 italic font-serif leading-relaxed">
                    &ldquo;{s.audio_script}&rdquo;
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        <p className="text-[11px] text-slate-500 italic mt-3">
          {storyboard.note}
        </p>
      </div>
    </Drawer>
  );
};
