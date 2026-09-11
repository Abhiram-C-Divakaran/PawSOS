import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { ExternalLink } from 'lucide-react';

interface MapViewProps {
  lat: number;
  lng: number;
  title?: string;
  zoom?: number;
  height?: string;
}

export const MapView: React.FC<MapViewProps> = ({
  lat,
  lng,
  title = 'Rescue Location',
  zoom = 15,
  height = '240px',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    const map = L.map(mapContainerRef.current, {
      zoomControl: true,
      scrollWheelZoom: false,
    }).setView([lat, lng], zoom);
    mapInstanceRef.current = map;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 19,
    }).addTo(map);

    const icon = L.divIcon({
      className: 'custom-rescue-marker',
      html: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
      iconSize: [32, 32],
      iconAnchor: [16, 32],
    });

    const marker = L.marker([lat, lng], { icon }).addTo(map);
    if (title) {
      marker.bindPopup(`<strong>${title}</strong><br/>Lat: ${lat}, Lng: ${lng}`);
    }

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [lat, lng, title, zoom]);

  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;

  return (
    <div className="relative rounded-xl overflow-hidden border border-gray-200 shadow-sm">
      <div ref={mapContainerRef} style={{ height, width: '100%' }} className="z-0" />
      <div className="absolute top-2 right-2 z-10">
        <a
          href={mapsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="bg-white/95 hover:bg-white text-brand-darkNavy text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow border border-gray-200 flex items-center gap-1 transition-colors"
        >
          <span>Open Directions</span>
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
};
