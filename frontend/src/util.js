// Small shared frontend helpers. Keep this file tiny.

// Google Earth Web URL with oblique 3D camera (60° tilt, 400m camera distance,
// 35° heading). Renders full 3D photogrammetry in major US metros; falls back
// to tilted satellite imagery elsewhere. Either way, the user gets a much
// better sense of roof shape than the Google Maps top-down view.
//
// URL format: /web/@LAT,LNG,ALTa,DISTd,HEADINGy,TILTt,ROLLr
export function googleEarthObliqueUrl (lat, lng) {
  if (lat == null || lng == null) return null
  return `https://earth.google.com/web/@${lat},${lng},0a,400d,35y,60t,0r`
}
