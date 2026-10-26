import { useEffect, useRef } from 'react';
import type { FC } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export interface MapPoint { id: string; name: string; lat: number; lon: number; score: number; label: string }

const colour = (score: number) => (score >= 60 ? '#10b981' : score >= 35 ? '#f5b301' : '#8a7a55');

/** Pins only businesses with real coordinates (never the city centre). OpenStreetMap tiles; click a pin to open the business. */
export const ResultsMap: FC<{ points: MapPoint[]; onPick: (id: string) => void }> = ({ points, onPick }) => {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!el.current || map.current) return;
    map.current = L.map(el.current, { scrollWheelZoom: false }).setView([20, 0], 2);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => { map.current?.remove(); map.current = null; layer.current = null; };
  }, []);

  useEffect(() => {
    if (!map.current || !layer.current) return;
    layer.current.clearLayers();
    const bounds: L.LatLngTuple[] = [];
    for (const p of points) {
      const marker = L.circleMarker([p.lat, p.lon], { radius: 8, color: '#3a2f14', weight: 1.5, fillColor: colour(p.score), fillOpacity: 0.9 })
        .bindTooltip(`${p.name} · ${Math.round(p.score)} · ${p.label}`).on('click', () => onPick(p.id));
      marker.addTo(layer.current);
      bounds.push([p.lat, p.lon]);
    }
    if (bounds.length) map.current.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
    setTimeout(() => map.current?.invalidateSize(), 50);
  }, [points, onPick]);

  return <div ref={el} className="h-80 w-full rounded-xl overflow-hidden border border-slate-800" role="img" aria-label={`Map of ${points.length} businesses`} />;
};
