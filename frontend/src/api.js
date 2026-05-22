// Thin API client. One file because the backend surface is small.

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function search ({ icao, radiusMiles, includeChains, hideContacted = true }) {
  const res = await fetch(`${BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      icao,
      radius_miles: radiusMiles,
      include_chains: includeChains,
      hide_contacted: hideContacted
    })
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    let message = `Search failed (${res.status})`
    try {
      const parsed = JSON.parse(text)
      message = parsed.detail || message
    } catch (e) {
      if (text) message = text
    }
    throw new Error(message)
  }
  return res.json()
}

export function csvUrl () {
  return `${BASE}/export.csv`
}

export async function downloadCsv ({ icao, radiusMiles, includeChains, hideContacted = false }) {
  const res = await fetch(`${BASE}/export.csv`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      icao,
      radius_miles: radiusMiles,
      include_chains: includeChains,
      hide_contacted: hideContacted
    })
  })
  if (!res.ok) {
    throw new Error(`CSV export failed (${res.status})`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `antenna_candidates_${icao}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function updateOutreachState (placeId, body) {
  const res = await fetch(`${BASE}/candidates/${encodeURIComponent(placeId)}/state`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Save failed (${res.status}): ${text}`)
  }
  return res.json()
}
