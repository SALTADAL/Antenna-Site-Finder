import React, { useEffect, useState } from 'react'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export default function PreflightBanner () {
  const [data, setData] = useState(null)
  const [dismissed, setDismissed] = useState(false)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function run () {
      try {
        const res = await fetch(`${BASE}/preflight`)
        const json = await res.json()
        if (!cancelled) setData(json)
      } catch (e) {
        if (!cancelled) {
          setData({
            overall_ok: false,
            mode: 'unknown',
            checks: [{ ok: false, label: 'Backend', detail: 'Could not reach the backend on :8000.' }]
          })
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    run()
    return () => { cancelled = true }
  }, [])

  if (loading || dismissed || !data) return null

  if (data.mode === 'mock') {
    return (
      <Banner tone='accent' onClose={() => setDismissed(true)}>
        <span className='font-bold'>Mock mode.</span>{' '}
        Running on local fixture data. Set
        {' '}<code className='inline-block px-1.5 py-0.5 rounded bg-accent-ink/15 text-[11px] font-mono'>APP_MODE=live</code>{' '}
        in .env and add your API keys to query real Places data.
      </Banner>
    )
  }

  if (data.overall_ok) {
    return (
      <Banner tone='good' onClose={() => setDismissed(true)}>
        <span className='font-bold'>Live mode ready.</span>{' '}
        All API keys validated · preflight ${data.total_cost_usd?.toFixed(4) ?? '0.0000'}.
      </Banner>
    )
  }

  return (
    <Banner tone='alert' onClose={() => setDismissed(true)}>
      <button
        onClick={() => setExpanded(!expanded)}
        className='text-left w-full'
      >
        <span className='font-bold'>API check failed.</span>{' '}
        Tap to {expanded ? 'hide' : 'show'} details.
      </button>
      {expanded && (
        <ul className='mt-2 space-y-1 text-xs'>
          {data.checks.map((c, i) => (
            <li key={i} className='flex gap-2'>
              <span>{c.ok ? '✓' : '✕'}</span>
              <span><strong>{c.label}:</strong> {c.detail}</span>
            </li>
          ))}
        </ul>
      )}
    </Banner>
  )
}

function Banner ({ tone, children, onClose }) {
  const palette = {
    accent: 'bg-accent text-accent-ink border-b border-accent-hover',
    good: 'bg-good-bg text-good border-b border-good/30',
    alert: 'bg-alert-bg text-alert border-b border-alert/30'
  }
  return (
    <div className={`px-5 sm:px-8 py-2.5 text-sm flex justify-between items-start gap-4 ${palette[tone]}`}>
      <div className='flex-1 max-w-6xl mx-auto w-full'>{children}</div>
      <button
        onClick={onClose}
        className='text-current/70 hover:text-current text-lg leading-none px-1 shrink-0'
        aria-label='Dismiss'
      >
        ✕
      </button>
    </div>
  )
}
