import React, { useMemo, useState } from 'react'
import { googleEarthObliqueUrl, candidateEarthQuery } from '../util.js'

// Column definitions. Each has a getter so we can sort uniformly.
const COLUMNS = [
  { key: 'rank', label: '#', get: (_, i) => i + 1, align: 'right', width: 'w-10' },
  { key: 'score', label: 'Score', get: (c) => c.score, align: 'right', width: 'w-16' },
  { key: 'status', label: 'Status', get: (c) => (c.outreach?.status || 'untouched'), align: 'left', width: 'w-24' },
  { key: 'name', label: 'Business', get: (c) => c.name, align: 'left', width: 'min-w-[14rem]' },
  { key: 'distance', label: 'Dist', get: (c) => c.distance_miles, align: 'right', width: 'w-16' },
  { key: 'roof_type', label: 'Roof', get: (c) => c.roof_type, align: 'left', width: 'w-20' },
  { key: 'roof_area', label: 'Area', get: (c) => c.roof_area_sqft || 0, align: 'right', width: 'w-20' },
  { key: 'height', label: 'Height', get: (c) => c.building_height_m || 0, align: 'right', width: 'w-20' },
  { key: 'chain', label: 'Type', get: (c) => (c.is_chain ? 'Chain' : 'Indie'), align: 'left', width: 'w-20' },
  { key: 'city', label: 'City', get: (c) => c.city, align: 'left', width: 'min-w-[8rem]' },
  { key: 'actions', label: '', get: () => 0, align: 'right', width: 'w-16', noSort: true }
]

// Status palette tuned for dark mode: muted background + bright text.
export const STATUS_OPTIONS = [
  { value: 'untouched', label: 'Untouched', cls: 'bg-status-untouched text-muted' },
  { value: 'contacted', label: 'Contacted', cls: 'bg-status-contacted/40 text-blue-300' },
  { value: 'followup', label: 'Follow up', cls: 'bg-status-followup/40 text-orange-300' },
  { value: 'interested', label: 'Interested', cls: 'bg-status-interested/40 text-good' },
  { value: 'declined', label: 'Declined', cls: 'bg-status-declined/40 text-bad' },
  { value: 'won', label: 'Won', cls: 'bg-accent text-accent-ink font-bold' },
  { value: 'lost', label: 'Lost', cls: 'bg-status-lost text-muted2' }
]

export function StatusBadge ({ status }) {
  const opt = STATUS_OPTIONS.find((o) => o.value === status) || STATUS_OPTIONS[0]
  return (
    <span className={`inline-block px-2 py-0.5 rounded-pill text-[11px] font-semibold ${opt.cls}`}>
      {opt.label}
    </span>
  )
}

export default function ResultsTable ({ candidates, onSelect }) {
  const [sort, setSort] = useState({ key: 'score', dir: 'desc' })

  const sorted = useMemo(() => {
    const col = COLUMNS.find((c) => c.key === sort.key)
    if (!col) return candidates
    const arr = [...candidates]
    arr.sort((a, b) => {
      const va = col.get(a, candidates.indexOf(a))
      const vb = col.get(b, candidates.indexOf(b))
      if (typeof va === 'string' && typeof vb === 'string') {
        return sort.dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
      }
      return sort.dir === 'asc' ? va - vb : vb - va
    })
    return arr
  }, [candidates, sort])

  function setSortKey (key) {
    const col = COLUMNS.find((c) => c.key === key)
    if (col?.noSort) return
    setSort((s) => ({ key, dir: s.key === key && s.dir === 'desc' ? 'asc' : 'desc' }))
  }

  if (!candidates.length) {
    return (
      <div className='py-16 text-center text-muted text-sm'>
        No candidates matched. Try a wider radius or turn off "Hide contacted".
      </div>
    )
  }

  return (
    <div className='overflow-auto thin-scroll'>
      <table className='w-full text-sm border-collapse'>
        <thead className='sticky top-0 bg-surface z-10'>
          <tr className='border-b border-border'>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-3 text-[10px] font-semibold text-muted uppercase tracking-[0.15em] whitespace-nowrap ${col.width} ${
                  col.align === 'right' ? 'text-right' : 'text-left'
                } ${col.noSort ? '' : 'cursor-pointer hover:text-ink transition'}`}
                onClick={() => setSortKey(col.key)}
              >
                <span className='inline-flex items-center gap-1'>
                  {col.label}
                  {sort.key === col.key && !col.noSort && (
                    <span className='text-[9px]'>{sort.dir === 'desc' ? '▼' : '▲'}</span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((c, i) => (
            <tr
              key={c.place_id}
              onClick={() => onSelect(c)}
              className='border-b border-border hover:bg-surface2 cursor-pointer transition'
            >
              <td className='px-3 py-3 text-right text-muted2 font-mono text-xs'>{i + 1}</td>
              <td className='px-3 py-3 text-right'>
                <ScoreChip score={c.score} />
              </td>
              <td className='px-3 py-3'>
                <StatusBadge status={c.outreach?.status || 'untouched'} />
              </td>
              <td className='px-3 py-3 text-ink font-semibold'>{c.name}</td>
              <td className='px-3 py-3 text-right text-ink tabular-nums'>{c.distance_miles.toFixed(1)}</td>
              <td className='px-3 py-3'>
                <RoofBadge type={c.roof_type} source={c.roof_source} />
              </td>
              <td className='px-3 py-3 text-right text-ink tabular-nums'>
                {c.roof_area_sqft ? Math.round(c.roof_area_sqft).toLocaleString() : '—'}
              </td>
              <td className='px-3 py-3 text-right text-ink tabular-nums'>
                {c.building_height_m ? `${c.building_height_m}m` : '—'}
              </td>
              <td className='px-3 py-3'>
                {c.is_chain ? (
                  <span className='inline-block px-2 py-0.5 rounded-pill text-[11px] font-semibold bg-bad-bg text-bad'>
                    Chain
                  </span>
                ) : (
                  <span className='inline-block px-2 py-0.5 rounded-pill text-[11px] font-semibold bg-good-bg text-good'>
                    Indie
                  </span>
                )}
              </td>
              <td className='px-3 py-3 text-muted text-xs'>
                {c.city}, {c.state}
              </td>
              <td className='px-3 py-3 text-right'>
                <EarthQuickButton candidate={c} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ScoreChip ({ score }) {
  // Score tiers tuned for dark mode contrast.
  const tier =
    score >= 70 ? 'bg-good-bg text-good border-good/40'
      : score >= 50 ? 'bg-warn-bg text-warn border-warn/40'
        : 'bg-bad-bg text-bad border-bad/40'
  return (
    <span className={`inline-flex items-center justify-center min-w-[2.75rem] h-7 px-2 rounded-pill text-xs font-bold border tabular-nums ${tier}`}>
      {score}
    </span>
  )
}

function EarthQuickButton ({ candidate }) {
  const url = googleEarthObliqueUrl(
    candidate.latitude,
    candidate.longitude,
    candidateEarthQuery(candidate)
  )
  if (!url) return null
  return (
    <a
      href={url}
      target='_blank'
      rel='noopener noreferrer'
      onClick={(e) => e.stopPropagation()}
      title='Open in Google Earth (oblique 3D view)'
      className='inline-flex items-center gap-1 px-2 py-1 rounded-pill text-[11px] font-semibold text-muted hover:text-accent bg-surface hover:bg-surface3 border border-border hover:border-accent/40 transition'
    >
      <GlobeIcon />
      3D
    </a>
  )
}

function GlobeIcon () {
  return (
    <svg
      width='11'
      height='11'
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
      aria-hidden='true'
    >
      <circle cx='12' cy='12' r='10' />
      <path d='M2 12h20' />
      <path d='M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z' />
    </svg>
  )
}

function RoofBadge ({ type, source }) {
  const palette = {
    flat: 'bg-good-bg text-good',
    mixed: 'bg-warn-bg text-warn',
    pitched: 'bg-bad-bg text-bad',
    unknown: 'bg-surface2 text-muted'
  }
  const label = type.charAt(0).toUpperCase() + type.slice(1)
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-pill text-[11px] font-semibold ${palette[type] || palette.unknown}`}
      title={source && source !== 'none' ? `Source: ${source}` : 'No roof data available'}
    >
      {label}
    </span>
  )
}
