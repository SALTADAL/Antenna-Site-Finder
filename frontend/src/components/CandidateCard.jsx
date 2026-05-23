import React, { useState } from 'react'
import { ScoreChip, StatusBadge, STATUS_OPTIONS } from './ResultsTable.jsx'
import { updateOutreachState } from '../api.js'
import { googleEarthObliqueUrl, candidateEarthQuery } from '../util.js'

export default function CandidateCard ({ candidate, airport, onClose, onOutreachUpdate }) {
  const c = candidate
  const phoneHref = c.phone ? `tel:${c.phone.replace(/[^\d+]/g, '')}` : null
  const breakdownEntries = Object.entries(c.score_breakdown || {})
  const earthUrl = googleEarthObliqueUrl(c.latitude, c.longitude, candidateEarthQuery(c))

  const [status, setStatus] = useState(c.outreach?.status || 'untouched')
  const [notes, setNotes] = useState(c.outreach?.notes || '')
  const [contactedBy, setContactedBy] = useState(c.outreach?.contacted_by || '')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [savedAt, setSavedAt] = useState(null)

  const dirty = (
    status !== (c.outreach?.status || 'untouched') ||
    notes !== (c.outreach?.notes || '') ||
    contactedBy !== (c.outreach?.contacted_by || '')
  )

  async function handleSave () {
    setSaving(true)
    setSaveError(null)
    try {
      const newState = await updateOutreachState(c.place_id, {
        status,
        notes,
        contacted_by: contactedBy,
        business_name: c.name,
        airport_icao: airport?.icao || ''
      })
      onOutreachUpdate?.(c.place_id, newState)
      setSavedAt(Date.now())
    } catch (err) {
      setSaveError(err.message || String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className='fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4'
      onClick={onClose}
    >
      <div
        className='bg-surface border border-border2 rounded-t-2xl sm:rounded-2xl w-full max-w-2xl max-h-[92vh] overflow-auto thin-scroll shadow-2xl'
        onClick={(e) => e.stopPropagation()}
      >
        <div className='p-6 border-b border-border flex items-start justify-between gap-4'>
          <div className='flex-1 min-w-0'>
            <div className='flex items-center gap-2 mb-3 flex-wrap'>
              <ScoreChip score={c.score} />
              {c.is_chain ? (
                <span className='inline-block px-2 py-0.5 rounded-pill text-[11px] font-semibold bg-bad-bg text-bad'>
                  Chain: {c.chain_match}
                </span>
              ) : (
                <span className='inline-block px-2 py-0.5 rounded-pill text-[11px] font-semibold bg-good-bg text-good'>
                  Independent
                </span>
              )}
              <StatusBadge status={c.outreach?.status || 'untouched'} />
            </div>
            <h2 className='text-xl sm:text-2xl font-black text-ink leading-tight tracking-tight'>{c.name}</h2>
            <p className='text-sm text-muted mt-1'>{c.address}</p>
          </div>
          <button
            onClick={onClose}
            className='text-muted hover:text-ink text-xl leading-none px-2 -mr-2'
            aria-label='Close'
          >
            ✕
          </button>
        </div>

        <div className='p-6 grid grid-cols-2 gap-x-6 gap-y-4 text-sm border-b border-border'>
          <Field label='Distance'>{c.distance_miles.toFixed(2)} mi from {airport?.icao}</Field>
          <Field label='Roof type'>
            <span className='capitalize'>{c.roof_type}</span>
            {c.roof_source && c.roof_source !== 'none' && (
              <span className='text-muted text-xs ml-1'>({c.roof_source})</span>
            )}
          </Field>
          <Field label='Roof area'>{c.roof_area_sqft ? `${Math.round(c.roof_area_sqft).toLocaleString()} sqft` : 'unknown'}</Field>
          <Field label='Building height'>{c.building_height_m ? `${c.building_height_m} m` : 'unknown'}</Field>
          <Field label='Phone'>
            {phoneHref ? (
              <a href={phoneHref} className='text-accent hover:underline font-semibold'>
                {c.phone}
              </a>
            ) : (
              <span className='text-muted'>not listed</span>
            )}
          </Field>
          <Field label='Rating'>
            {c.rating != null ? `${c.rating}★ (${c.user_ratings_total || 0} reviews)` : 'not rated'}
          </Field>
        </div>

        {c.note && (
          <div className='p-6 border-b border-border bg-surface2/40'>
            <div className='text-[10px] font-semibold text-muted uppercase tracking-[0.15em] mb-1'>Field-ops note</div>
            <p className='text-sm text-ink'>{c.note}</p>
          </div>
        )}

        <div className='p-6 border-b border-border'>
          <div className='text-[10px] font-semibold text-muted uppercase tracking-[0.15em] mb-3'>Outreach</div>
          <div className='grid grid-cols-2 gap-3 mb-3'>
            <div>
              <label htmlFor='status' className='block text-[10px] font-semibold text-muted uppercase tracking-wider mb-1'>
                Status
              </label>
              <select
                id='status'
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className='w-full bg-surface2 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent transition'
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value} className='bg-surface'>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor='contactedBy' className='block text-[10px] font-semibold text-muted uppercase tracking-wider mb-1'>
                Contacted by
              </label>
              <input
                id='contactedBy'
                type='text'
                value={contactedBy}
                onChange={(e) => setContactedBy(e.target.value)}
                placeholder='Your name (optional)'
                className='w-full bg-surface2 border border-border rounded-lg px-3 py-2 text-sm placeholder:text-muted2 focus:outline-none focus:border-accent transition'
              />
            </div>
          </div>
          <label htmlFor='notes' className='block text-[10px] font-semibold text-muted uppercase tracking-wider mb-1'>
            Notes
          </label>
          <textarea
            id='notes'
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder='What happened on the call. Owner name, gate code, follow-up date, anything.'
            className='w-full bg-surface2 border border-border rounded-lg px-3 py-2 text-sm placeholder:text-muted2 focus:outline-none focus:border-accent transition resize-y'
          />
          {c.outreach?.last_contact_at && (
            <p className='mt-2 text-xs text-muted'>
              Last contact: {new Date(c.outreach.last_contact_at * 1000).toLocaleString()}
            </p>
          )}
          <div className='mt-3 flex items-center gap-3'>
            <button
              type='button'
              onClick={handleSave}
              disabled={!dirty || saving}
              className='rounded-lg bg-accent text-accent-ink hover:bg-accent-hover text-sm font-bold px-4 py-2 transition disabled:opacity-50 disabled:cursor-not-allowed'
            >
              {saving ? 'Saving...' : 'Save status'}
            </button>
            {savedAt && !dirty && (
              <span className='text-xs text-good font-semibold'>Saved.</span>
            )}
            {saveError && (
              <span className='text-xs text-alert'>{saveError}</span>
            )}
          </div>
        </div>

        {breakdownEntries.length > 0 && (
          <div className='p-6 border-b border-border'>
            <div className='text-[10px] font-semibold text-muted uppercase tracking-[0.15em] mb-3'>Score breakdown</div>
            <ul className='grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm'>
              {breakdownEntries.map(([k, v]) => (
                <li key={k} className='flex justify-between'>
                  <span className='text-muted capitalize'>{k.replace(/_/g, ' ')}</span>
                  <span className='font-bold text-ink tabular-nums'>{v}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className='p-6 flex flex-wrap gap-3'>
          {phoneHref && (
            <a
              href={phoneHref}
              className='rounded-pill bg-accent text-accent-ink hover:bg-accent-hover font-bold px-4 py-2 text-sm transition'
            >
              Call {c.phone}
            </a>
          )}
          {c.google_maps_url && (
            <a
              href={c.google_maps_url}
              target='_blank'
              rel='noopener noreferrer'
              className='rounded-pill border border-border bg-surface2 hover:border-border2 hover:bg-surface3 text-ink font-semibold px-4 py-2 text-sm transition'
            >
              Open in Google Maps
            </a>
          )}
          {earthUrl && (
            <a
              href={earthUrl}
              target='_blank'
              rel='noopener noreferrer'
              title='Opens Google Earth Web with the camera tilted 60° over the building. 3D photogrammetry renders in major US metros.'
              className='rounded-pill border border-border bg-surface2 hover:border-accent/40 hover:bg-surface3 text-ink font-semibold px-4 py-2 text-sm transition'
            >
              Open in Google Earth (3D)
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

function Field ({ label, children }) {
  return (
    <div>
      <div className='text-[10px] font-semibold text-muted uppercase tracking-[0.15em] mb-0.5'>
        {label}
      </div>
      <div className='text-ink'>{children}</div>
    </div>
  )
}
