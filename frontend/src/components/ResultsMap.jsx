import React from 'react'
import { MapContainer, TileLayer, CircleMarker, Marker, Tooltip } from 'react-leaflet'
import L from 'leaflet'

// Airport marker: yellow on black to match the brand palette.
const airportIcon = L.divIcon({
  className: '',
  html: `<div style="width:26px;height:26px;border-radius:50%;background:#FFCD00;color:#0a0a0a;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:14px;border:2px solid #000;box-shadow:0 2px 6px rgba(0,0,0,0.6)">✈</div>`,
  iconSize: [26, 26],
  iconAnchor: [13, 13]
})

function colorForScore (score) {
  if (score >= 70) return '#4ADE80'
  if (score >= 50) return '#FB923C'
  return '#F87171'
}

export default function ResultsMap ({ airport, candidates, onSelect }) {
  const center = [airport.latitude, airport.longitude]
  return (
    <MapContainer center={center} zoom={11} scrollWheelZoom className='w-full h-full'>
      {/* CartoDB Dark Matter tiles. Free, dark, well-suited to overlays. */}
      <TileLayer
        attribution='&copy; OpenStreetMap &copy; CARTO'
        url='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
        subdomains='abcd'
        maxZoom={19}
      />
      <Marker position={center} icon={airportIcon}>
        <Tooltip direction='top' offset={[0, -10]}>
          <div className='text-xs'>
            <div className='font-bold'>{airport.icao}</div>
            <div className='text-muted'>{airport.name}</div>
          </div>
        </Tooltip>
      </Marker>
      {candidates.map((c) => (
        <CircleMarker
          key={c.place_id}
          center={[c.latitude, c.longitude]}
          radius={8}
          pathOptions={{
            color: colorForScore(c.score),
            fillColor: colorForScore(c.score),
            fillOpacity: 0.85,
            weight: 2
          }}
          eventHandlers={{ click: () => onSelect(c) }}
        >
          <Tooltip direction='top' offset={[0, -8]}>
            <div className='text-xs'>
              <div className='font-bold text-ink'>{c.name}</div>
              <div className='text-muted'>Score {c.score} · {c.distance_miles.toFixed(1)} mi</div>
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
