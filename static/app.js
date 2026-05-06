/* Hedera TradeRoot — frontend */

const TYPE_COLOURS = {
  nursery:          '#2d9e4e',
  garden_centre:    '#e63f8a',
  hard_landscaper:  '#d23232',
  soils_aggregates: '#c8860a',
  timber:           '#7b4f2e',
  furniture:        '#4169e1',
  tools:            '#e07b00',
  lighting:         '#8a2be2',
  other:            '#888888',
};

const TYPE_LABELS = {
  nursery:          'Nursery',
  garden_centre:    'Garden Centre',
  hard_landscaper:  'Hard Landscaper',
  soils_aggregates: 'Soils & Aggregates',
  timber:           'Timber',
  furniture:        'Furniture',
  tools:            'Tools',
  lighting:         'Lighting',
  other:            'Other',
};

// UK + Ireland bounds
const UK_BOUNDS  = L.latLngBounds([[49.5, -11.0], [61.0, 2.5]]);
const UK_CENTER  = [54.5, -4.0];
const COUNTY_BOUNDS = {
  London: [[51.28, -0.52], [51.70, 0.34]],
  Surrey: [[51.06, -0.91], [51.52, 0.18]],
  'West Sussex': [[50.73, -0.99], [51.15, 0.29]],
  'East Sussex': [[50.74, -0.04], [51.10, 0.81]],
  Kent: [[51.05, 0.05], [51.46, 1.46]],
  Hampshire: [[50.70, -1.93], [51.27, -0.84]],
  Hertfordshire: [[51.60, -0.65], [51.98, 0.25]],
  Essex: [[51.45, 0.04], [52.05, 1.42]],
  Berkshire: [[51.30, -1.60], [51.65, -0.55]],
  Buckinghamshire: [[51.50, -1.25], [52.05, -0.40]],
  Oxfordshire: [[51.44, -1.78], [52.12, -0.90]],
  Bedfordshire: [[51.85, -0.82], [52.35, 0.05]],
  'Isle of Wight': [[50.57, -1.62], [50.77, -1.00]],
};
const countyViewCache = new Map();
const COUNTY_BORDERS_PREF_KEY = 'traderoot:showCountyBorders';

// Maps our pipeline county names → one or more GeoJSON feature names
// Needed where counties are split into unitary authorities or London boroughs
const COUNTY_GEOJSON_MAP = {
  London: [
    'Barking and Dagenham', 'Barnet', 'Bexley', 'Brent', 'Bromley', 'Camden',
    'City of London', 'Croydon', 'Ealing', 'Enfield', 'Greenwich', 'Hackney',
    'Hammersmith and Fulham', 'Haringey', 'Harrow', 'Havering', 'Hillingdon',
    'Hounslow', 'Islington', 'Kensington and Chelsea', 'Kingston upon Thames',
    'Lambeth', 'Lewisham', 'Merton', 'Newham', 'Redbridge', 'Richmond upon Thames',
    'Southwark', 'Sutton', 'Tower Hamlets', 'Waltham Forest', 'Wandsworth', 'Westminster',
  ],
  'East Sussex': ['East Sussex', 'Brighton and Hove'],
  Berkshire: ['Bracknell Forest', 'Reading', 'Slough', 'West Berkshire', 'Windsor and Maidenhead', 'Wokingham'],
  Bedfordshire: ['Bedford', 'Central Bedfordshire', 'Luton'],
};

// ── State ─────────────────────────────────────────────────────────────────────
let map, markersLayer;
let allSuppliers    = [];
let proximityRaw    = null;
let proximityCenter = null;
let proximityAbortController = null;
let radiusCircle    = null;
let homeMarker      = null;
let radiusDebounce  = null;
let countyBoundsLayer = null;
let countyBoundaryLayers = new Map();
let activeTypes     = new Set();
let activeAreas     = new Set();
let searchQuery     = '';
let showTrade       = true;
let showNonTrade    = true;

function setCountyHoverLabel(name = '') {
  const el = document.getElementById('county-hover-label');
  if (!el) return;
  el.textContent = name ? `Hover: ${name}` : '';
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initTabs();
  initMap();
  const [suppliers, areas] = await Promise.all([
    apiFetch('/api/map'),
    apiFetch('/api/areas'),
  ]);
  allSuppliers = suppliers;
  buildTypePills();
  populateAreaOptions(suppliers, areas);
  initSearch();
  initPostcodeSearch();
  applyFilters();
  initAddForm();
  initRegisterForm();
  initModal();
  handleDeepLink();
});

// ── Tabs ──────────────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
      if (btn.dataset.tab === 'map') map.invalidateSize();
    });
  });
}

// ── Map ───────────────────────────────────────────────────────────────────────
function initMap() {
  map = L.map('map', {
    zoomControl:          true,
    maxBounds:            UK_BOUNDS,
    maxBoundsViscosity:   1.0,
    minZoom:              5,
    zoomSnap:             0.0,
  }).setView(UK_CENTER, 6);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© <a href="https://carto.com">CartoDB</a> © <a href="https://openstreetmap.org">OpenStreetMap</a>',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(map);

  markersLayer = L.layerGroup().addTo(map);
  initCountyBoundsLayer();
}

async function initCountyBoundsLayer() {
  countyBoundsLayer = L.layerGroup().addTo(map);

  const defaultStyle = {
    color: '#0c6b47', weight: 1.5, opacity: 0.65, fillOpacity: 0.04,
    fillColor: '#0c6b47', dashArray: '6 5',
  };

  try {
    const res = await fetch('/data/counties.geojson');
    if (!res.ok) throw new Error('not found');
    const geojson = await res.json();

    L.geoJSON(geojson, {
      style: () => ({ ...defaultStyle }),
      interactive: true,
      onEachFeature: (feature, layer) => {
        const name = feature.properties.CTYUA24NM
                  || feature.properties.CTYUA23NM
                  || feature.properties.CTYUA22NM
                  || feature.properties.ctyua23nm
                  || feature.properties.name
                  || feature.properties.NAME;
        if (!name) return;
        layer.on('mouseover', () => setCountyHoverLabel(name));
        layer.on('mouseout', () => setCountyHoverLabel(''));
        countyBoundaryLayers.set(name, layer);
      },
    }).addTo(countyBoundsLayer);

  } catch {
    // GeoJSON not yet downloaded — fall back to bounding boxes
    Object.entries(COUNTY_BOUNDS).forEach(([name, bounds]) => {
      const rect = L.rectangle(bounds, { ...defaultStyle, interactive: true });
      rect.on('mouseover', () => setCountyHoverLabel(name));
      rect.on('mouseout', () => setCountyHoverLabel(''));
      rect.addTo(countyBoundsLayer);
      countyBoundaryLayers.set(name, rect);
    });
  }

  const toggle = document.getElementById('county-borders-toggle');
  if (toggle) {
    const savedPref = localStorage.getItem(COUNTY_BORDERS_PREF_KEY);
    const showBorders = savedPref == null ? true : savedPref === 'true';
    toggle.checked = showBorders;

    if (!showBorders) {
      map.removeLayer(countyBoundsLayer);
    }

    toggle.addEventListener('change', () => {
      if (toggle.checked) map.addLayer(countyBoundsLayer);
      else map.removeLayer(countyBoundsLayer);
      localStorage.setItem(COUNTY_BORDERS_PREF_KEY, String(toggle.checked));
    });
  }
}

function updateCountyBoundaryHighlight(areaName) {
  countyBoundaryLayers.forEach(layer => {
    layer.setStyle({
      color: '#0c6b47', weight: 1.5, opacity: 0.65,
      fillOpacity: 0.04, fillColor: '#0c6b47', dashArray: '6 5',
    });
  });

  if (!areaName) return;

  // Resolve to one or more GeoJSON feature names
  const targets = COUNTY_GEOJSON_MAP[areaName]
    ?? COUNTY_GEOJSON_MAP[Object.keys(COUNTY_GEOJSON_MAP).find(k => k.toLowerCase() === areaName.toLowerCase())]
    ?? [areaName];

  targets.forEach(target => {
    const layer = countyBoundaryLayers.get(target)
      || [...countyBoundaryLayers.entries()].find(([k]) => k.toLowerCase() === target.toLowerCase())?.[1];
    if (!layer) return;
    layer.setStyle({
      color: '#c0392b', weight: 3, opacity: 0.95,
      fillOpacity: 0.06, fillColor: '#c0392b', dashArray: null,
    });
  });
}

function makeCircleMarker(s, includeDistance) {
  const colour = TYPE_COLOURS[s.type] || '#888';
  const label  = TYPE_LABELS[s.type]  || s.type;
  const dist   = includeDistance && s.distance_miles != null
    ? `<br>📍 ${s.distance_miles} mi` : '';

  const rating = s.avg_rating ? `⭐ ${s.avg_rating}` : 'No reviews';

  const marker = L.circleMarker([s.latitude, s.longitude], {
    radius: 7, fillColor: colour, color: '#fff', weight: 1.5, fillOpacity: 0.85,
  });
  marker.bindTooltip(`<b>${esc(s.name)}</b><br>${label} · ${rating}${dist}`, { sticky: true });
  marker.on('click', () => openDetail(s.id));
  return marker;
}

function makeHomeMarker(lat, lon) {
  const icon = L.divIcon({
    className: 'home-location-marker',
    html: `
      <div class="home-location-marker__badge" aria-hidden="true">
        <svg viewBox="0 0 24 24" role="presentation" focusable="false">
          <path d="M12 3.4 4 10v10h5.7v-5.8h4.6V20H20V10z"></path>
        </svg>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });

  return L.marker([lat, lon], { icon }).bindTooltip('Your location');
}

// ── Pills & search ────────────────────────────────────────────────────────────
function buildTypePills() {
  const container = document.getElementById('type-pills');
  Object.entries(TYPE_LABELS).forEach(([type, label]) => {
    const btn = document.createElement('button');
    btn.className    = 'filter-pill';
    btn.dataset.type = type;
    btn.innerHTML    = `<span class="pill-dot" style="background:${TYPE_COLOURS[type]}"></span>${label}`;
    btn.addEventListener('click', () => {
      activeTypes.has(type) ? activeTypes.delete(type) : activeTypes.add(type);
      const on = activeTypes.has(type);
      btn.classList.toggle('active', on);
      btn.style.background  = on ? TYPE_COLOURS[type] : '';
      btn.style.borderColor = on ? TYPE_COLOURS[type] : '';
      btn.style.color       = on ? '#fff' : '';
      applyFilters();
    });
    container.appendChild(btn);
  });
}

function buildAreaPills(areas) {
  const container = document.getElementById('area-pills');
  areas.forEach(name => {
    const btn = document.createElement('button');
    btn.className = 'filter-pill area-pill';
    btn.textContent = name;
    btn.addEventListener('click', () => {
      activeAreas.has(name) ? activeAreas.delete(name) : activeAreas.add(name);
      btn.classList.toggle('active', activeAreas.has(name));
      if (!proximityRaw) applyFilters();
    });
    container.appendChild(btn);
  });
}

function getPopulatedAreas(suppliers) {
  const names = new Set();
  suppliers.forEach(s => (s.areas || []).forEach(a => names.add(a)));
  return [...names].sort((a, b) => a.localeCompare(b));
}

function populateAreaOptions(suppliers, allAreas) {
  const addAreasEl = document.getElementById('add-areas');
  const mapAreaFilterEl = document.getElementById('map-area-filter');

  allAreas.forEach(name => {
    addAreasEl.appendChild(new Option(name, name));
  });

  getPopulatedAreas(suppliers).forEach(name => {
    mapAreaFilterEl.appendChild(new Option(name, name));
  });

  mapAreaFilterEl.addEventListener('change', () => {
    if (proximityRaw) clearProximityState();
    applyFilters();
  });
}

function initSearch() {
  document.getElementById('supplier-search').addEventListener('input', e => {
    searchQuery = e.target.value.trim().toLowerCase();
    if (searchQuery && proximityRaw) clearProximityState();
    applyFilters();
  });

  const tradeYesInput = document.getElementById('trade-filter-yes');
  const tradeNoInput = document.getElementById('trade-filter-no');
  tradeYesInput.addEventListener('change', () => {
    showTrade = tradeYesInput.checked;
    applyFilters();
  });
  tradeNoInput.addEventListener('change', () => {
    showNonTrade = tradeNoInput.checked;
    applyFilters();
  });
}

// ── Client-side filtering ─────────────────────────────────────────────────────
async function focusSelectedCounty(areaName) {
  if (!areaName || proximityRaw) return;

  if (COUNTY_BOUNDS[areaName]) {
    map.fitBounds(L.latLngBounds(COUNTY_BOUNDS[areaName]), { padding: [40, 40], maxZoom: 10 });
    return;
  }

  if (countyViewCache.has(areaName)) {
    const { lat, lon } = countyViewCache.get(areaName);
    map.setView([lat, lon], 9);
    return;
  }

  try {
    const query = encodeURIComponent(`${areaName}, UK`);
    const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${query}&format=jsonv2&limit=1`, {
      headers: { Accept: 'application/json' },
    });
    const results = await res.json();
    const first = results?.[0];
    if (!first) return;

    const lat = Number(first.lat);
    const lon = Number(first.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

    countyViewCache.set(areaName, { lat, lon });
    map.setView([lat, lon], 9);
  } catch {
    // Leave the current view unchanged if geocoding fails.
  }
}

function applyFilters() {
  const areaVal = document.getElementById('map-area-filter')?.value || '';
  updateCountyBoundaryHighlight(areaVal);
  let list = proximityRaw ?? allSuppliers;
  if (activeTypes.size) list = list.filter(s => activeTypes.has(s.type));
  if (areaVal && !proximityRaw)
    list = list.filter(s => (s.areas || []).includes(areaVal));
  list = list.filter(s => (showTrade && !!s.trade) || (showNonTrade && !s.trade));
  if (searchQuery) list = list.filter(s => s.name.toLowerCase().includes(searchQuery));

  markersLayer.clearLayers();
  list.forEach(s => makeCircleMarker(s, !!proximityRaw).addTo(markersLayer));
  renderResults(list, !!proximityRaw);
  setStatus(`${list.length} supplier${list.length !== 1 ? 's' : ''}`);

  if (!proximityRaw && areaVal) {
    if (list.length) {
      const bounds = L.latLngBounds(list.map(s => [s.latitude, s.longitude]));
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 });
    } else {
      void focusSelectedCounty(areaVal);
    }
  } else if (!proximityRaw && !areaVal) {
    map.setView(UK_CENTER, 6);
  }
}

async function refreshSuppliers() {
  allSuppliers = await apiFetch('/api/map');
  applyFilters();
}

async function loadProximityMap() {
  if (!proximityCenter) return;
  const { lat, lon } = proximityCenter;
  const radius = +document.getElementById('radius-slider').value;
  const requestKey = `${lat}:${lon}:${radius}`;
  document.body.dataset.proximityRequestKey = requestKey;

  if (proximityAbortController) proximityAbortController.abort();
  proximityAbortController = new AbortController();

  let all;
  try {
    all = await apiFetch(`/api/map/near?${new URLSearchParams({ lat, lon, radius })}`, {
      signal: proximityAbortController.signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') return;
    throw err;
  }

  if (document.body.dataset.proximityRequestKey !== requestKey) {
    return;
  }
  proximityAbortController = null;
  proximityRaw = all;
  document.getElementById('map-area-filter').value = '';
  document.getElementById('supplier-search').value = '';
  searchQuery = '';

  if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
  if (homeMarker)   { map.removeLayer(homeMarker);   homeMarker   = null; }

  radiusCircle = L.circle([lat, lon], {
    radius: radius * 1609.34,
    color: '#888', weight: 1.5, fillColor: '#888', fillOpacity: 0.04,
  }).addTo(map);
  map.fitBounds(radiusCircle.getBounds(), { padding: [4, 4] });

  homeMarker = makeHomeMarker(lat, lon).addTo(map);

  applyFilters();
  setStatus(`${proximityRaw.length} suppliers within ${radius} miles`);
}

// ── Postcode search ───────────────────────────────────────────────────────────
function initPostcodeSearch() {
  document.getElementById('postcode-btn').addEventListener('click', searchPostcode);
  document.getElementById('postcode-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') searchPostcode();
  });
  document.getElementById('postcode-clear').addEventListener('click', clearPostcode);
  document.getElementById('geolocate-btn').addEventListener('click', geolocate);

  document.getElementById('radius-slider').addEventListener('input', e => {
    document.getElementById('radius-label').textContent = e.target.value + ' mi';
    clearTimeout(radiusDebounce);
    radiusDebounce = setTimeout(loadProximityMap, 400);
  });

}

async function searchPostcode() {
  const raw = document.getElementById('postcode-input').value.trim();
  if (!raw) return;
  setStatus('Looking up postcode…');
  const pc = raw.replace(/\s+/g, '');

  try {
    const data = await apiFetch(`/api/postcode/${encodeURIComponent(pc)}`);

    proximityCenter = { lat: data.latitude, lon: data.longitude };
    map.setView([proximityCenter.lat, proximityCenter.lon], 10);
    document.getElementById('radius-row').style.display   = '';
    document.getElementById('postcode-clear').style.display = '';
    loadProximityMap();
  } catch (err) {
    setStatus(`⚠️ ${err.detail || 'Could not look up postcode right now.'}`);
  }
}

const GEOLOCATION_CACHE_KEY = 'traderoot:last-location';
const GEOLOCATION_CACHE_MAX_AGE_MS = 15 * 60 * 1000;
let geolocateStatusTimer = null;

function readCachedLocation() {
  try {
    const cached = JSON.parse(localStorage.getItem(GEOLOCATION_CACHE_KEY) || 'null');
    if (!cached) return null;
    const ageMs = Date.now() - cached.timestamp;
    if (!Number.isFinite(cached.lat) || !Number.isFinite(cached.lon) || ageMs > GEOLOCATION_CACHE_MAX_AGE_MS) {
      return null;
    }
    return cached;
  } catch {
    return null;
  }
}

function writeCachedLocation(coords) {
  try {
    localStorage.setItem(GEOLOCATION_CACHE_KEY, JSON.stringify({
      lat: coords.latitude,
      lon: coords.longitude,
      accuracy: coords.accuracy ?? null,
      timestamp: Date.now(),
    }));
  } catch {
    // Ignore storage failures; they should not block geolocation.
  }
}

function applyProximityCenter(lat, lon) {
  proximityCenter = { lat, lon };
  document.getElementById('postcode-input').value = '';
  map.setView([lat, lon], 10);
  document.getElementById('radius-row').style.display = '';
  document.getElementById('postcode-clear').style.display = '';
  loadProximityMap();
}

function geolocate() {
  if (!window.isSecureContext) {
    setStatus('⚠️ Location requires HTTPS on mobile browsers.');
    return;
  }
  if (!navigator.geolocation) { setStatus('⚠️ Geolocation not supported.'); return; }
  const btn = document.getElementById('geolocate-btn');
  btn.textContent = '⏳ Locating…';
  btn.disabled = true;
  let hasAppliedCachedLocation = false;
  let elapsed = 0;
  let statusTimer = null;

  const cached = readCachedLocation();
  if (cached) {
    hasAppliedCachedLocation = true;
    applyProximityCenter(cached.lat, cached.lon);
    setStatus('Using recent location… refreshing precise fix.');
    btn.textContent = '⏳ Refreshing…';
  }

  if (!hasAppliedCachedLocation) {
    statusTimer = setInterval(() => {
      elapsed += 200;
      const dots = '.'.repeat((Math.floor(elapsed / 500) % 3) + 1);
      setStatus(`Getting location${dots}`);
    }, 200);
  }

  const getPosition = options => new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, options);
  });

  getPosition({ maximumAge: 300000, timeout: 1500, enableHighAccuracy: false })
    .catch(() => {
      if (!hasAppliedCachedLocation) {
        setStatus('Still locating… trying more precise fix.');
      }
      return getPosition({ maximumAge: 0, timeout: 6000, enableHighAccuracy: true });
    })
    .then(pos => {
      if (statusTimer) clearInterval(statusTimer);
      btn.textContent = '📍 My location';
      btn.disabled = false;
      writeCachedLocation(pos.coords);
      applyProximityCenter(pos.coords.latitude, pos.coords.longitude);
    })
    .catch(() => {
      if (statusTimer) clearInterval(statusTimer);
      btn.textContent = '📍 My location';
      btn.disabled = false;
      if (!hasAppliedCachedLocation) {
        setStatus('⚠️ Could not get location — check browser permissions.');
      }
    });
}

function clearProximityState() {
  if (proximityAbortController) {
    proximityAbortController.abort();
    proximityAbortController = null;
  }
  delete document.body.dataset.proximityRequestKey;
  proximityRaw    = null;
  proximityCenter = null;
  document.getElementById('postcode-input').value         = '';
  document.getElementById('radius-row').style.display     = 'none';
  document.getElementById('postcode-clear').style.display = 'none';
  if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
  if (homeMarker)   { map.removeLayer(homeMarker);   homeMarker   = null; }
}

function clearPostcode() {
  clearProximityState();
  map.setView(UK_CENTER, 6);
  applyFilters();
}

// ── Results list ──────────────────────────────────────────────────────────────
const RESULTS_CAP = 100;

function renderResults(suppliers, showDist) {
  const el = document.getElementById('map-results');
  if (!suppliers.length) {
    el.innerHTML = '<p style="color:#888;padding:8px">No suppliers found.</p>';
    return;
  }
  const capped   = suppliers.slice(0, RESULTS_CAP);
  const overflow = suppliers.length > RESULTS_CAP
    ? `<p style="color:#888;font-size:13px;padding:4px 8px">Showing ${RESULTS_CAP} of ${suppliers.length} — filter to narrow results.</p>`
    : '';
  el.innerHTML = overflow + capped.map(s => supplierCardHTML(s, showDist)).join('');
  el.querySelectorAll('.supplier-card').forEach(card => {
    card.addEventListener('click', () => openDetail(+card.dataset.id));
  });
}

// ── Supplier card HTML ────────────────────────────────────────────────────────
function supplierCardHTML(s, showDist) {
  const label  = TYPE_LABELS[s.type] || s.type;
  const badge  = `<span class="type-badge badge-${s.type}">${label}</span>`;
  const rating = s.avg_rating ? `⭐ ${s.avg_rating} (${s.review_count})` : 'no reviews';
  const dist   = showDist && s.distance_miles != null ? ` · ${s.distance_miles} mi` : '';
  return `
    <div class="supplier-card" data-id="${s.id}">
      <div class="card-header">
        <div>
          <div class="card-name">${esc(s.name)}</div>
          <div class="card-meta">${rating}${dist}</div>
        </div>
        ${badge}
      </div>
    </div>`;
}

// ── Detail modal ──────────────────────────────────────────────────────────────
function initModal() {
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.querySelector('.modal-backdrop').addEventListener('click', closeModal);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

async function openDetail(id) {
  document.getElementById('modal').classList.remove('hidden');
  document.getElementById('modal-body').innerHTML = '<p style="padding:20px;color:#888">Loading…</p>';

  const [s, designers, allCats] = await Promise.all([
    apiFetch(`/api/suppliers/${id}`),
    apiFetch('/api/designers'),
    apiFetch('/api/categories'),
  ]);

  document.getElementById('modal-body').innerHTML = detailHTML(s, designers, allCats);
  wireDetailEvents(s, designers, allCats);
  history.replaceState(null, '', `?supplier=${id}`);
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
  history.replaceState(null, '', '/');
}

function detailHTML(s, designers, allCats) {
  const label  = TYPE_LABELS[s.type] || s.type;
  const rating = s.avg_rating ? `⭐ ${s.avg_rating} (${s.review_count} reviews)` : 'No reviews yet';

  const living      = allCats.filter(c => c.group_name === 'Living');
  const nonliving   = allCats.filter(c => c.group_name === 'Non-living');
  const assignedIds = new Set((s.categories || []).map(c => c.id));

  const catCheckboxes = group => group.map(c => `
    <label class="cat-checkbox">
      <input type="checkbox" name="cat" value="${c.id}" ${assignedIds.has(c.id) ? 'checked' : ''}>
      ${esc(c.name)}
    </label>`).join('');

  const reviewsHTML = (s.reviews || []).length
    ? s.reviews.map(r => `
        <div class="review-item">
          <div class="review-stars">${'⭐'.repeat(r.rating)}</div>
          <div>${esc(r.review_text)}</div>
          <div class="review-meta">${esc(r.designer)}${r.designer_company ? ' · ' + esc(r.designer_company) : ''} · ${r.job_area || ''} · ${r.created_at.slice(0,10)}</div>
        </div>`).join('')
    : '<p style="font-size:13px;color:#888">No reviews yet.</p>';

  const designerOptions = designers.map(d =>
    `<option value="${d.id}">${esc(d.name)}${d.company ? ' · ' + esc(d.company) : ''}</option>`
  ).join('');

  const typeOptions = Object.entries(TYPE_LABELS).map(([val, txt]) =>
    `<option value="${val}" ${s.type === val ? 'selected' : ''}>${txt}</option>`
  ).join('');
  const hasDirectionsTarget = (Number.isFinite(s.latitude) && Number.isFinite(s.longitude)) || !!s.address;

  return `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <input id="name-input" type="text" value="${esc(s.name)}" style="font-size:1.15rem;font-weight:700;flex:1;color:var(--text)">
      <button class="btn-ghost" id="save-name-btn" style="font-size:12px;padding:5px 10px;white-space:nowrap">Save</button>
      <span id="name-msg" class="form-msg" style="font-size:12px"></span>
    </div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
      <select id="type-select" style="font-size:13px">${typeOptions}</select>
      <button class="btn-ghost" id="save-type-btn" style="font-size:12px;padding:5px 10px">Save</button>
      <span id="type-msg" class="form-msg" style="font-size:12px"></span>
    </div>
    <div class="detail-row">${rating}</div>
    ${s.phone   ? `<div class="detail-row">📞 <strong>${esc(s.phone)}</strong></div>` : ''}
    ${s.email   ? `<div class="detail-row">📧 ${esc(s.email)}</div>` : ''}
    ${s.website ? `<div class="detail-row">🌐 <a href="${esc(s.website)}" target="_blank" rel="noopener">${esc(s.website)}</a></div>` : ''}
    ${s.address ? `<div class="detail-row">🧭 ${esc(s.address)}</div>` : ''}
    ${hasDirectionsTarget ? `<div class="detail-row"><button class="btn-primary" id="directions-btn" type="button">Directions</button><span id="directions-msg" class="form-msg" style="font-size:12px;margin-left:8px"></span></div>` : ''}
    ${(() => {
      const primary    = s.primary_area;
      const secondary  = (s.areas || []).filter(a => a !== primary);
      const secondaryStr = secondary.length ? ` <span style="color:#888;font-size:0.88em">(also: ${secondary.map(esc).join(', ')})</span>` : '';
      return primary
        ? `<div class="detail-row">📍 <strong>${esc(primary)}</strong>${secondaryStr}</div>`
        : s.areas && s.areas.length
          ? `<div class="detail-row">📍 ${s.areas.map(esc).join(', ')}</div>`
          : '';
    })()}
    ${s.notes   ? `<div class="detail-row">📝 ${esc(s.notes)}</div>` : ''}

    ${allCats.length ? `
    <div class="modal-section">
      <h3>Categories</h3>
      <div class="category-group"><h4>🌿 Living</h4>${catCheckboxes(living)}</div>
      <div class="category-group"><h4>🪨 Non-living</h4>${catCheckboxes(nonliving)}</div>
      <button class="btn-primary" id="save-cats-btn" style="margin-top:8px">Save categories</button>
      <p id="cat-msg" class="form-msg"></p>
    </div>` : ''}

    <div class="modal-section">
      <h3>Reviews</h3>
      <div id="reviews-container">${reviewsHTML}</div>
      ${designers.length ? `
      <details style="margin-top:12px">
        <summary style="font-size:13px;cursor:pointer;color:var(--green-mid)">✍️ Leave a review</summary>
        <div class="review-form">
          <label>Your name<select id="rev-designer">${designerOptions}</select></label>
          <label>Rating
            <select id="rev-rating">
              <option value="5">⭐⭐⭐⭐⭐</option>
              <option value="4">⭐⭐⭐⭐</option>
              <option value="3" selected>⭐⭐⭐</option>
              <option value="2">⭐⭐</option>
              <option value="1">⭐</option>
            </select>
          </label>
          <label>County<input id="rev-area" type="text" placeholder="e.g. Surrey"></label>
          <label>Review<textarea id="rev-text" rows="3" placeholder="Your experience…"></textarea></label>
          <button class="btn-primary" id="submit-review-btn">Submit</button>
          <p id="rev-msg" class="form-msg"></p>
        </div>
      </details>` : '<p style="font-size:12px;color:#888;margin-top:8px">Register as a designer to leave a review.</p>'}
    </div>

    <div class="modal-section">
      <button class="btn-danger" id="delete-btn">Delete supplier</button>
      <div id="delete-confirm" style="display:none;margin-top:8px">
        <p style="font-size:13px;color:#c0392b;margin-bottom:8px">Are you sure? This cannot be undone.</p>
        <button class="btn-danger" id="delete-confirm-btn">Yes, delete</button>
        <button class="btn-ghost" id="delete-cancel-btn" style="margin-left:8px">Cancel</button>
      </div>
    </div>`;
}

function wireDetailEvents(s, designers, allCats) {
  const directionsBtn = document.getElementById('directions-btn');
  if (directionsBtn) {
    directionsBtn.addEventListener('click', () => openDirections(s));
  }

  const saveNameBtn = document.getElementById('save-name-btn');
  if (saveNameBtn) {
    saveNameBtn.addEventListener('click', async () => {
      const newName = document.getElementById('name-input').value.trim();
      if (!newName) return;
      saveNameBtn.disabled = true;
      try {
        await apiFetch(`/api/suppliers/${s.id}`, {
          method: 'PATCH', body: JSON.stringify({ name: newName }),
        });
        const msg = document.getElementById('name-msg');
        msg.textContent = 'Saved!';
        msg.className   = 'form-msg success';
        setTimeout(() => { msg.textContent = ''; }, 2000);
        s.name = newName;
        refreshSuppliers();
      } finally {
        saveNameBtn.disabled = false;
      }
    });
  }

  const saveTypeBtn = document.getElementById('save-type-btn');
  if (saveTypeBtn) {
    saveTypeBtn.addEventListener('click', async () => {
      const newType = document.getElementById('type-select').value;
      saveTypeBtn.disabled = true;
      try {
        await apiFetch(`/api/suppliers/${s.id}`, {
          method: 'PATCH', body: JSON.stringify({ type: newType }),
        });
        const msg = document.getElementById('type-msg');
        msg.textContent = 'Saved!';
        msg.className   = 'form-msg success';
        setTimeout(() => { msg.textContent = ''; }, 2000);
        s.type = newType;
        refreshSuppliers();
      } finally {
        saveTypeBtn.disabled = false;
      }
    });
  }

  const saveCatsBtn = document.getElementById('save-cats-btn');
  if (saveCatsBtn) {
    saveCatsBtn.addEventListener('click', async () => {
      const ids = [...document.querySelectorAll('input[name="cat"]:checked')].map(el => +el.value);
      saveCatsBtn.disabled = true;
      try {
        await apiFetch(`/api/suppliers/${s.id}/categories`, {
          method: 'PUT', body: JSON.stringify({ category_ids: ids }),
        });
        const msg = document.getElementById('cat-msg');
        msg.textContent = 'Saved!';
        msg.className   = 'form-msg success';
        setTimeout(() => { msg.textContent = ''; }, 2000);
      } finally {
        saveCatsBtn.disabled = false;
      }
    });
  }

  const submitRevBtn = document.getElementById('submit-review-btn');
  if (submitRevBtn) {
    submitRevBtn.addEventListener('click', async () => {
      const text = document.getElementById('rev-text').value.trim();
      if (!text) { document.getElementById('rev-msg').textContent = 'Please write a review.'; return; }
      await apiFetch(`/api/suppliers/${s.id}/reviews`, {
        method: 'POST',
        body: JSON.stringify({
          designer_id: +document.getElementById('rev-designer').value,
          rating:      +document.getElementById('rev-rating').value,
          review_text: text,
          job_area:    document.getElementById('rev-area').value || null,
        }),
      });
      document.getElementById('rev-msg').textContent = 'Review submitted — thank you!';
      document.getElementById('rev-msg').className   = 'form-msg success';
      const updated = await apiFetch(`/api/suppliers/${s.id}`);
      document.getElementById('reviews-container').innerHTML = (updated.reviews || []).map(r => `
        <div class="review-item">
          <div class="review-stars">${'⭐'.repeat(r.rating)}</div>
          <div>${esc(r.review_text)}</div>
          <div class="review-meta">${esc(r.designer)} · ${r.job_area || ''} · ${r.created_at.slice(0,10)}</div>
        </div>`).join('');
    });
  }

  document.getElementById('delete-btn').addEventListener('click', () => {
    document.getElementById('delete-confirm').style.display = '';
  });
  document.getElementById('delete-cancel-btn').addEventListener('click', () => {
    document.getElementById('delete-confirm').style.display = 'none';
  });
  document.getElementById('delete-confirm-btn').addEventListener('click', async () => {
    await apiFetch(`/api/suppliers/${s.id}`, { method: 'DELETE' });
    closeModal();
    loadMapSuppliers();
  });
}

function getSupplierDirectionsUrl(supplier, origin) {
  const destination = Number.isFinite(supplier.latitude) && Number.isFinite(supplier.longitude)
    ? `${supplier.latitude},${supplier.longitude}`
    : supplier.address;

  if (!destination) return null;

  const ua = navigator.userAgent || '';
  const platform = navigator.platform || '';
  const isAppleMobile = /iPhone|iPad|iPod/i.test(ua)
    || (platform === 'MacIntel' && navigator.maxTouchPoints > 1);

  if (isAppleMobile) {
    const params = new URLSearchParams({
      daddr: destination,
      dirflg: 'd',
    });
    if (origin) {
      params.set('saddr', `${origin.lat},${origin.lon}`);
    }
    return `https://maps.apple.com/?${params.toString()}`;
  }

  const params = new URLSearchParams({
    api: '1',
    destination,
    travelmode: 'driving',
  });

  if (origin) {
    params.set('origin', `${origin.lat},${origin.lon}`);
  }

  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

function openDirections(supplier) {
  const msg = document.getElementById('directions-msg');
  const openTarget = origin => {
    const url = getSupplierDirectionsUrl(supplier, origin);
    if (!url) {
      if (msg) msg.textContent = 'No address available for directions.';
      return;
    }
    window.open(url, '_blank', 'noopener');
  };

  if (!window.isSecureContext || !navigator.geolocation) {
    openTarget(null);
    return;
  }

  if (msg) msg.textContent = 'Getting your location…';
  navigator.geolocation.getCurrentPosition(
    pos => {
      if (msg) msg.textContent = '';
      openTarget({ lat: pos.coords.latitude, lon: pos.coords.longitude });
    },
    () => {
      if (msg) msg.textContent = 'Opening destination only.';
      openTarget(null);
    },
    { maximumAge: 300000, timeout: 4000, enableHighAccuracy: false }
  );
}

// ── Add Supplier form ─────────────────────────────────────────────────────────
function initAddForm() {
  document.getElementById('add-form').addEventListener('submit', async e => {
    e.preventDefault();
    const fd    = new FormData(e.target);
    const areas = [...document.getElementById('add-areas').selectedOptions].map(o => o.value);
    const body  = {
      name:       fd.get('name'),
      type:       fd.get('type'),
      website:    fd.get('website')    || null,
      phone:      fd.get('phone')      || null,
      email:      fd.get('email')      || null,
      address:    fd.get('address')    || null,
      postcode:   fd.get('postcode')   || null,
      price_band: fd.get('price_band') || null,
      notes:      fd.get('notes')      || null,
      areas,
    };
    const msg = document.getElementById('add-msg');
    try {
      await apiFetch('/api/suppliers', { method: 'POST', body: JSON.stringify(body) });
      msg.textContent = `${body.name} added successfully!`;
      msg.className   = 'form-msg success';
      e.target.reset();
      await refreshSuppliers();
    } catch (err) {
      msg.textContent = err.detail || 'Something went wrong — please try again.';
      msg.className   = 'form-msg error';
    }
  });
}

// ── Register form ─────────────────────────────────────────────────────────────
function initRegisterForm() {
  document.getElementById('register-form').addEventListener('submit', async e => {
    e.preventDefault();
    const fd   = new FormData(e.target);
    const body = { name: fd.get('name'), email: fd.get('email'), company: fd.get('company') || null };
    const msg  = document.getElementById('register-msg');
    try {
      await apiFetch('/api/designers', { method: 'POST', body: JSON.stringify(body) });
      msg.textContent = `Welcome, ${body.name}! You can now leave reviews.`;
      msg.className   = 'form-msg success';
      e.target.reset();
    } catch (err) {
      msg.textContent = err.status === 409 ? 'That email is already registered.' : 'Something went wrong.';
      msg.className   = 'form-msg error';
    }
  });
}


// ── Deep link ─────────────────────────────────────────────────────────────────
function handleDeepLink() {
  const id = new URLSearchParams(location.search).get('supplier');
  if (id) openDetail(+id);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(msg) {
  document.getElementById('map-status').textContent = msg;
}

function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    try {
      const payload = await res.json();
      if (payload && typeof payload.detail === 'string') err.detail = payload.detail;
    } catch {
      // Ignore non-JSON error responses.
    }
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}
