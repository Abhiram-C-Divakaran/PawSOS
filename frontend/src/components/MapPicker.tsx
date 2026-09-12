import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { MapPin, Crosshair, AlertCircle } from 'lucide-react';

interface MapPickerProps {
  initialLat?: number;
  initialLng?: number;
  onLocationSelect: (coords: { lat: number; lng: number; addressText?: string }) => void;
}

export const MapPicker: React.FC<MapPickerProps> = ({
  initialLat,
  initialLng,
  onLocationSelect,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const onLocationSelectRef = useRef(onLocationSelect);

  useEffect(() => {
    onLocationSelectRef.current = onLocationSelect;
  }, [onLocationSelect]);

  const [hasLocation, setHasLocation] = useState<boolean>(!!(initialLat && initialLng));
  const [detecting, setDetecting] = useState<boolean>(false);
  const [geoError, setGeoError] = useState<string>('');

  const createIcon = () => {
    return L.divIcon({
      className: 'custom-rescue-marker',
      html: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
      iconSize: [32, 32],
      iconAnchor: [16, 32],
    });
  };

  useEffect(() => {
    if (!mapContainerRef.current) return;

    const startLat = initialLat || 20.5937;
    const startLng = initialLng || 78.9629;
    const startZoom = initialLat && initialLng ? 16 : 5;

    const map = L.map(mapContainerRef.current).setView([startLat, startLng], startZoom);
    mapInstanceRef.current = map;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    if (initialLat && initialLng) {
      const marker = L.marker([initialLat, initialLng], {
        draggable: true,
        icon: createIcon(),
      }).addTo(map);

      marker.on('dragend', () => {
        const pos = marker.getLatLng();
        setHasLocation(true);
        onLocationSelectRef.current({
          lat: Number(pos.lat.toFixed(6)),
          lng: Number(pos.lng.toFixed(6)),
        });
      });

      markerRef.current = marker;
    }

    map.on('click', (e: L.LeafletMouseEvent) => {
      const { lat, lng } = e.latlng;
      const cleanLat = Number(lat.toFixed(6));
      const cleanLng = Number(lng.toFixed(6));

      if (markerRef.current) {
        markerRef.current.setLatLng([cleanLat, cleanLng]);
      } else {
        const marker = L.marker([cleanLat, cleanLng], {
          draggable: true,
          icon: createIcon(),
        }).addTo(map);

        marker.on('dragend', () => {
          const pos = marker.getLatLng();
          onLocationSelectRef.current({
            lat: Number(pos.lat.toFixed(6)),
            lng: Number(pos.lng.toFixed(6)),
          });
        });

        markerRef.current = marker;
      }

      setHasLocation(true);
      setGeoError('');
      onLocationSelectRef.current({ lat: cleanLat, lng: cleanLng });
    });

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      markerRef.current = null;
    };
  }, [initialLat, initialLng]);

  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      setGeoError('Geolocation is not supported by your browser. Please click directly on the map.');
      return;
    }

    setDetecting(true);
    setGeoError('');

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setDetecting(false);
        const lat = Number(position.coords.latitude.toFixed(6));
        const lng = Number(position.coords.longitude.toFixed(6));

        if (mapInstanceRef.current) {
          mapInstanceRef.current.setView([lat, lng], 16);

          if (markerRef.current) {
            markerRef.current.setLatLng([lat, lng]);
          } else {
            const marker = L.marker([lat, lng], {
              draggable: true,
              icon: createIcon(),
            }).addTo(mapInstanceRef.current);

            marker.on('dragend', () => {
              const pos = marker.getLatLng();
              onLocationSelectRef.current({
                lat: Number(pos.lat.toFixed(6)),
                lng: Number(pos.lng.toFixed(6)),
              });
            });

            markerRef.current = marker;
          }
        }

        setHasLocation(true);
        onLocationSelectRef.current({
          lat,
          lng,
          addressText: `GPS Coordinates: ${lat}, ${lng}`,
        });
      },
      (_err) => {
        setDetecting(false);
        setGeoError(
          'Location access was denied or timed out. Please tap or click on the map to place the location pin.'
        );
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <button
          type="button"
          onClick={handleDetectLocation}
          disabled={detecting}
          className="bg-brand-softMint border border-brand-teal text-brand-teal px-4 py-2.5 rounded-lg font-semibold flex items-center justify-center hover:bg-teal-50 transition-colors shadow-sm text-sm"
        >
          <Crosshair className={`w-4 h-4 mr-2 ${detecting ? 'animate-spin' : ''}`} />
          {detecting ? 'Locating device...' : 'Detect My Exact Location'}
        </button>

        <span className="text-xs text-gray-500 text-center sm:text-right">
          Or click/drag marker on the map to pinpoint
        </span>
      </div>

      {geoError && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 p-3 rounded-lg text-sm flex items-start">
          <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0 mt-0.5 text-amber-600" />
          <span>{geoError}</span>
        </div>
      )}

      <div
        ref={mapContainerRef}
        className="w-full h-72 rounded-xl border border-gray-200 overflow-hidden shadow-inner z-0"
        style={{ minHeight: '280px' }}
      />

      {!hasLocation && (
        <p className="text-xs text-rose-600 font-medium flex items-center">
          <MapPin className="w-3.5 h-3.5 mr-1" />
          Please pinpoint the location on the map or click 'Detect My Exact Location' to continue.
        </p>
      )}
    </div>
  );
};
