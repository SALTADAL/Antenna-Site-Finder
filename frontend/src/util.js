// Small shared frontend helpers. Keep this file tiny.

// Google Earth Web URL with oblique 3D camera (60° tilt, 400m camera distance,
// 35° heading) AND a populated search query so the search bar shows the
// candidate and a pin drops on its location.
//
// Two-part URL structure:
//   /web/search/{QUERY}   tells Google Earth to run a search, drop a pin,
//                         and populate the left-rail search bar with QUERY
//   /@{LAT},{LNG},...     positions the camera at the candidate's coords
//                         with the requested altitude / distance / heading / tilt
//
// When `query` is omitted we fall back to the lat,lng as the search term,
// which still drops a pin but shows raw coordinates in the search bar.
export function googleEarthObliqueUrl (lat, lng, query) {
  if (lat == null || lng == null) return null
  const searchTerm = query && query.trim() ? query.trim() : `${lat},${lng}`
  const encoded = encodeURIComponent(searchTerm)
  return `https://earth.google.com/web/search/${encoded}/@${lat},${lng},0a,400d,35y,60t,0r`
}

// Convenience: build a search query from a candidate that combines the
// business name with the formatted address. Falls back gracefully if one
// or the other is missing.
export function candidateEarthQuery (candidate) {
  if (!candidate) return ''
  const parts = []
  if (candidate.name) parts.push(candidate.name)
  if (candidate.address) parts.push(candidate.address)
  return parts.join(', ')
}
