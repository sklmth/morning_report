import { ArrowUpRight, Compass } from 'lucide-react';
import type { NextStop } from '@/types/site';

type NextStopBlockProps = { stop: NextStop };

export function NextStopBlock({ stop }: NextStopBlockProps) {
  return (
    <aside className="next-stop-block">
      <div><p className="eyebrow">下一枚坐标 / Next pin</p><h3 className="display">{stop.city}</h3><p>{stop.country} · {stop.coordinates}</p></div>
      <div className="next-stop-reason"><Compass size={19} aria-hidden /><p>{stop.reason}</p></div>
      <span className="next-stop-window">{stop.window} <ArrowUpRight size={15} aria-hidden /></span>
    </aside>
  );
}
