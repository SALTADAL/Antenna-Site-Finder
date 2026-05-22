import React from 'react'

export default function SearchForm ({
  icao,
  setIcao,
  radius,
  setRadius,
  includeChains,
  setIncludeChains,
  hideContacted,
  setHideContacted,
  loading,
  onSubmit,
  error
}) {
  return (
    <form onSubmit={onSubmit} className='flex flex-col gap-4'>
      <div className='flex flex-col sm:flex-row gap-3 items-stretch'>
        {/* Big bold airport-code input */}
        <div className='flex-1'>
          <label htmlFor='icao' className='block text-[11px] font-semibold text-muted uppercase tracking-[0.15em] mb-1.5'>
            Airport code
          </label>
          <input
            id='icao'
            type='text'
            autoComplete='off'
            autoCapitalize='characters'
            spellCheck='false'
            value={icao}
            onChange={(e) => setIcao(e.target.value.toUpperCase())}
            placeholder='KRDU'
            maxLength={4}
            className='w-full bg-surface border border-border rounded-lg px-4 py-3 text-2xl font-black tracking-tight uppercase placeholder:text-muted2 focus:outline-none focus:border-accent transition'
          />
        </div>

        {/* Radius slider */}
        <div className='flex-1'>
          <div className='flex justify-between items-baseline mb-1.5'>
            <label htmlFor='radius' className='block text-[11px] font-semibold text-muted uppercase tracking-[0.15em]'>
              Radius
            </label>
            <span className='text-xl font-black tabular-nums leading-none'>{radius}<span className='text-xs text-muted font-semibold ml-1'>mi</span></span>
          </div>
          <input
            id='radius'
            type='range'
            min='1'
            max='25'
            step='1'
            value={radius}
            onChange={(e) => setRadius(parseInt(e.target.value, 10))}
            className='w-full accent-accent mt-3'
          />
          <div className='flex justify-between text-[10px] text-muted2 mt-1 uppercase tracking-wider'>
            <span>1</span>
            <span>25</span>
          </div>
        </div>

        {/* CTA. Yellow primary, matches the ATC app's banner color. */}
        <div className='flex items-end'>
          <button
            type='submit'
            disabled={loading}
            className='w-full sm:w-auto rounded-lg bg-accent text-accent-ink hover:bg-accent-hover transition font-bold text-base px-7 py-3 disabled:opacity-60 disabled:cursor-not-allowed'
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </div>

      {/* Filter toggles as pill chips */}
      <div className='flex flex-wrap gap-2'>
        <FilterPill
          active={!includeChains}
          onClick={() => setIncludeChains(!includeChains)}
          label='Hide chains'
          hint={includeChains ? 'Chains visible' : 'Chains hidden'}
        />
        <FilterPill
          active={hideContacted}
          onClick={() => setHideContacted(!hideContacted)}
          label='Hide contacted'
          hint={hideContacted ? 'History hidden' : 'History visible'}
        />
      </div>

      {error && (
        <div className='rounded-lg border border-alert/40 bg-alert-bg text-alert text-sm px-4 py-3'>
          {error}
        </div>
      )}
    </form>
  )
}

function FilterPill ({ active, onClick, label, hint }) {
  return (
    <button
      type='button'
      onClick={onClick}
      title={hint}
      className={`rounded-pill px-3.5 py-1.5 text-xs font-semibold border transition flex items-center gap-2 ${
        active
          ? 'bg-accent text-accent-ink border-accent'
          : 'bg-surface text-muted border-border hover:text-ink hover:border-border2'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-accent-ink' : 'bg-muted2'}`} />
      {label}
    </button>
  )
}
