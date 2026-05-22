import React, { useState, useEffect } from 'react'
import SearchForm from './components/SearchForm.jsx'
import ResultsTable from './components/ResultsTable.jsx'
import ResultsMap from './components/ResultsMap.jsx'
import CandidateCard from './components/CandidateCard.jsx'
import PreflightBanner from './components/PreflightBanner.jsx'
import { search, downloadCsv } from './api.js'

const RECENT_KEY = 'asf.recent_airports'
const MAX_RECENT = 6

export default function App () {
  const [icao, setIcao] = useState('KRDU')
  const [radius, setRadius] = useState(15)
  const [includeChains, setIncludeChains] = useState(false)
  const [hideContacted, setHideContacted] = useState(true)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [searchStartedAt, setSearchStartedAt] = useState(null)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('table')
  const [selected, setSelected] = useState(null)
  const [downloadingCsv, setDownloadingCsv] = useState(false)
  const [recent, setRecent] = useState([])

  // Load recent searches from localStorage on mount.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(RECENT_KEY)
      if (raw) setRecent(JSON.parse(raw))
    } catch (e) {
      // ignore parse errors
    }
  }, [])

  function pushRecent (airport) {
    setRecent((prev) => {
      const filtered = prev.filter((a) => a.icao !== airport.icao)
      const next = [
        { icao: airport.icao, city: airport.city, name: airport.name },
        ...filtered
      ].slice(0, MAX_RECENT)
      try {
        localStorage.setItem(RECENT_KEY, JSON.stringify(next))
      } catch (e) {
        // ignore storage errors
      }
      return next
    })
  }

  async function handleSearch (e, icaoOverride) {
    if (e && e.preventDefault) e.preventDefault()
    const targetIcao = (icaoOverride || icao || '').trim().toUpperCase()
    if (!targetIcao || targetIcao.length < 3) {
      setError('Enter a 3 or 4 letter airport code (KRDU, RDU, KCLT).')
      return
    }
    if (icaoOverride) setIcao(targetIcao)
    setError(null)
    setLoading(true)
    setSearchStartedAt(Date.now())
    setResult(null)
    setSelected(null)

    try {
      const payload = await search({
        icao: targetIcao,
        radiusMiles: radius,
        includeChains,
        hideContacted
      })
      setResult(payload)
      pushRecent(payload.airport)
      setTab('table')
    } catch (err) {
      setError(err.message || String(err))
    } finally {
      setLoading(false)
      setSearchStartedAt(null)
    }
  }

  async function handleDownload () {
    if (!result) return
    setDownloadingCsv(true)
    try {
      await downloadCsv({
        icao: result.airport.icao,
        radiusMiles: result.radius_miles,
        includeChains,
        hideContacted: false // CSV gets EVERYTHING so the user has a paper trail
      })
    } catch (err) {
      setError(err.message || String(err))
    } finally {
      setDownloadingCsv(false)
    }
  }

  function handleOutreachUpdate (placeId, newState) {
    if (!result) return
    setResult({
      ...result,
      candidates: result.candidates.map((c) =>
        c.place_id === placeId ? { ...c, outreach: newState } : c
      )
    })
    setSelected((curr) =>
      curr && curr.place_id === placeId ? { ...curr, outreach: newState } : curr
    )
  }

  return (
    <div className='min-h-screen bg-bg text-ink flex flex-col'>
      <Header />
      <PreflightBanner />

      <main className='flex-1 flex flex-col'>
        {/* HERO: search controls + airport-code pills */}
        <section className='border-b border-border'>
          <div className='max-w-6xl mx-auto px-5 sm:px-8 py-6 sm:py-8 flex flex-col gap-6'>
            <SearchPanel
              icao={icao}
              setIcao={setIcao}
              radius={radius}
              setRadius={setRadius}
              includeChains={includeChains}
              setIncludeChains={setIncludeChains}
              hideContacted={hideContacted}
              setHideContacted={setHideContacted}
              loading={loading}
              onSubmit={handleSearch}
              error={error}
            />
            {recent.length > 0 && (
              <RecentAirports
                recent={recent}
                active={result?.airport?.icao}
                onPick={(code) => handleSearch(null, code)}
              />
            )}
          </div>
        </section>

        {/* RESULTS */}
        <section className='flex-1 flex flex-col'>
          {loading && <LoadingPanel startedAt={searchStartedAt} />}
          {!loading && !result && <EmptyState />}
          {!loading && result && (
            <ResultsView
              result={result}
              tab={tab}
              setTab={setTab}
              onSelect={setSelected}
              onDownload={handleDownload}
              downloadingCsv={downloadingCsv}
            />
          )}
        </section>
      </main>

      {selected && (
        <CandidateCard
          candidate={selected}
          airport={result?.airport}
          onClose={() => setSelected(null)}
          onOutreachUpdate={handleOutreachUpdate}
        />
      )}
    </div>
  )
}

function Header () {
  return (
    <header className='sticky top-0 z-30 bg-bg/95 backdrop-blur border-b border-border'>
      <div className='max-w-6xl mx-auto px-5 sm:px-8 py-3.5 flex items-center justify-between'>
        <div className='flex items-center gap-3'>
          <div className='w-8 h-8 bg-accent text-accent-ink rounded-md flex items-center justify-center font-black text-base'>
            A
          </div>
          <div>
            <h1 className='text-base font-bold leading-tight tracking-tight'>Antenna Site Finder</h1>
            <p className='text-[11px] text-muted leading-tight uppercase tracking-wider'>Enhanced Radar field ops</p>
          </div>
        </div>
        <a
          href='http://localhost:8000/docs'
          target='_blank'
          rel='noopener noreferrer'
          className='text-xs text-muted hover:text-ink transition'
          title='Interactive API docs'
        >
          API
        </a>
      </div>
    </header>
  )
}

function SearchPanel ({
  icao, setIcao, radius, setRadius,
  includeChains, setIncludeChains,
  hideContacted, setHideContacted,
  loading, onSubmit, error
}) {
  return (
    <SearchForm
      icao={icao}
      setIcao={setIcao}
      radius={radius}
      setRadius={setRadius}
      includeChains={includeChains}
      setIncludeChains={setIncludeChains}
      hideContacted={hideContacted}
      setHideContacted={setHideContacted}
      loading={loading}
      onSubmit={onSubmit}
      error={error}
    />
  )
}

function RecentAirports ({ recent, active, onPick }) {
  return (
    <div className='flex flex-col gap-2'>
      <div className='text-[11px] font-semibold text-muted uppercase tracking-[0.15em]'>For you</div>
      <div className='-mx-1 overflow-x-auto thin-scroll'>
        <div className='inline-flex gap-2 px-1 min-w-full'>
          {recent.map((a) => (
            <button
              key={a.icao}
              onClick={() => onPick(a.icao)}
              className={`shrink-0 min-w-[110px] sm:min-w-[140px] text-left rounded-lg border transition px-4 py-3 hover:border-accent/60 hover:bg-surface ${
                active === a.icao ? 'border-accent bg-surface' : 'border-border bg-surface/40'
              }`}
            >
              <div className='text-2xl sm:text-3xl font-black tracking-tight leading-none'>{a.icao}</div>
              <div className='text-xs text-muted mt-1.5 truncate'>{a.city || a.name}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function ResultsView ({ result, tab, setTab, onSelect, onDownload, downloadingCsv }) {
  return (
    <div className='max-w-6xl w-full mx-auto px-5 sm:px-8 py-6 flex flex-col gap-5'>
      <AirportHeadline result={result} onDownload={onDownload} downloadingCsv={downloadingCsv} />
      <ResultsMeta result={result} />
      <TabBar tab={tab} setTab={setTab} count={result.candidate_count} />
      <div className='border border-border rounded-lg overflow-hidden bg-surface/40'>
        {tab === 'table' && (
          <div className='min-h-[60vh]'>
            <ResultsTable candidates={result.candidates} onSelect={onSelect} />
          </div>
        )}
        {tab === 'map' && (
          <div className='h-[60vh]'>
            <ResultsMap
              airport={result.airport}
              candidates={result.candidates.slice(0, 50)}
              onSelect={onSelect}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function AirportHeadline ({ result, onDownload, downloadingCsv }) {
  return (
    <div className='flex flex-wrap items-end justify-between gap-4'>
      <div className='min-w-0'>
        <div className='text-display-xl sm:text-[5.5rem] font-black tracking-tight leading-[0.95]'>
          {result.airport.icao}
        </div>
        <p className='mt-2 text-sm text-muted'>
          {result.airport.name} · {result.airport.city}, {result.airport.state}
        </p>
      </div>
      <button
        onClick={onDownload}
        disabled={downloadingCsv}
        className='rounded-pill bg-accent text-accent-ink hover:bg-accent-hover transition px-5 py-2.5 text-sm font-semibold disabled:opacity-60'
      >
        {downloadingCsv ? 'Preparing CSV...' : 'Download CSV'}
      </button>
    </div>
  )
}

function ResultsMeta ({ result }) {
  const cost = result.cost?.total_usd ?? 0
  const byApi = result.cost?.by_api ?? {}
  const outreach = result.outreach_counts || {}
  const hidden = outreach.hidden || 0
  return (
    <div className='flex flex-wrap gap-2'>
      <MetaChip label='New' value={result.candidate_count} accent />
      <MetaChip label='Radius' value={`${result.radius_miles} mi`} />
      {hidden > 0 && <MetaChip label='Hidden' value={hidden} />}
      <MetaChip label='API spend' value={`$${cost.toFixed(4)}`} />
      {Object.entries(byApi).map(([api, v]) => (
        <MetaChip
          key={api}
          label={api.replace(/_/g, ' ')}
          value={`${v.calls} · $${v.spend_usd.toFixed(3)}`}
        />
      ))}
      {result.mock_mode && (
        <MetaChip label='Mode' value='Mock fixtures' warn />
      )}
    </div>
  )
}

function MetaChip ({ label, value, accent, warn }) {
  const cls = accent
    ? 'bg-accent/15 text-accent border-accent/40'
    : warn
      ? 'bg-warn-bg text-warn border-warn/30'
      : 'bg-surface border-border text-ink'
  return (
    <div className={`rounded-pill border px-3 py-1 text-xs flex items-baseline gap-2 ${cls}`}>
      <span className='uppercase tracking-wider text-[10px] opacity-80'>{label}</span>
      <span className='font-semibold tabular-nums'>{value}</span>
    </div>
  )
}

function TabBar ({ tab, setTab, count }) {
  const TabButton = ({ id, label }) => (
    <button
      onClick={() => setTab(id)}
      className={`rounded-pill px-4 py-2 text-sm font-semibold transition ${
        tab === id
          ? 'bg-ink text-bg'
          : 'bg-surface text-muted hover:text-ink hover:bg-surface2 border border-border'
      }`}
    >
      {label}
    </button>
  )
  return (
    <div className='flex items-center justify-between gap-3'>
      <div className='flex gap-2'>
        <TabButton id='table' label='Table' />
        <TabButton id='map' label='Map' />
      </div>
      <div className='text-xs text-muted uppercase tracking-wider'>{count} candidates</div>
    </div>
  )
}

function LoadingPanel ({ startedAt }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!startedAt) return
    const interval = setInterval(() => {
      setElapsed((Date.now() - startedAt) / 1000)
    }, 250)
    return () => clearInterval(interval)
  }, [startedAt])

  const elapsedStr = elapsed < 60
    ? `${elapsed.toFixed(1)}s`
    : `${Math.floor(elapsed / 60)}m ${Math.floor(elapsed % 60)}s`

  let phase = 'Running pipeline'
  let hint = 'Calling Google Places to fetch nearby businesses.'
  if (elapsed > 8) {
    phase = 'Enriching candidates'
    hint = 'Pulling Place Details for each survivor.'
  }
  if (elapsed > 18) {
    phase = 'Analyzing roofs'
    hint = 'Solar API + OSM Overpass in parallel. Usually the longest stage.'
  }
  if (elapsed > 40) {
    phase = 'Vision fallback'
    hint = 'Claude is classifying roofs Solar could not see.'
  }
  if (elapsed > 90) {
    phase = 'Still going'
    hint = 'Longer than usual. Check the backend logs for a per-stage timing line.'
  }

  return (
    <div className='flex-1 flex items-center justify-center min-h-[50vh] py-12'>
      <div className='max-w-md w-full px-6 text-center'>
        <div className='inline-flex items-center gap-3 mb-5 px-3 py-1.5 rounded-pill bg-accent/15 text-accent border border-accent/30'>
          <div className='w-2 h-2 bg-accent rounded-full animate-pulse' />
          <span className='text-xs font-semibold uppercase tracking-wider'>{phase}</span>
        </div>
        <div className='text-display-xl font-black text-ink tabular-nums leading-none'>
          {elapsedStr}
        </div>
        <p className='text-sm text-muted mt-4 mb-6'>{hint}</p>
        <p className='text-xs text-muted2 max-w-sm mx-auto'>
          Typical first search: 30 to 90 seconds depending on radius. Repeat searches finish in under 5 seconds because every API call is cached.
        </p>
      </div>
    </div>
  )
}

function EmptyState () {
  return (
    <div className='flex-1 flex items-center justify-center min-h-[50vh] py-12'>
      <div className='max-w-md text-center px-6'>
        <div className='w-14 h-14 bg-surface2 border border-border rounded-xl mx-auto mb-5 flex items-center justify-center text-accent text-2xl'>
          ✈
        </div>
        <h2 className='text-2xl font-bold mb-2 tracking-tight'>Search an airport</h2>
        <p className='text-sm text-muted'>
          Enter a 4 letter ICAO (KRDU, KCLT, KSFO) or 3 letter IATA (RDU, CLT, SFO) to get a ranked list of nearby rooftop antenna host candidates.
        </p>
      </div>
    </div>
  )
}
