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
  nursery:          'Nursery (trade)',
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

// ── State ─────────────────────────────────────────────────────────────────────
let map, markersLayer;
let proximityCenter = null;
let radiusCircle    = null;
let homeMarker      = null;
let radiusDebounce  = null;

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initTabs();
  initMap();
  await populateAreaSelects();
  loadMapSuppliers();
  initPostcodeSearch();
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

async function loadMapSuppliers() {
  const type = document.getElementById('map-type-filter').value;
  const area = document.getElementById('map-area-filter').value;
  const params = new URLSearchParams();
  if (type) params.set('type', type);
  if (area) params.set('area', area);

  const suppliers = await apiFetch(`/api/map?${params}`);
  markersLayer.clearLayers();
  suppliers.forEach(s => makeCircleMarker(s, false).addTo(markersLayer));
  setStatus(`${suppliers.length} suppliers on map`);
  renderResults(suppliers, false);

  if (area && suppliers.length) {
    const bounds = L.latLngBounds(suppliers.map(s => [s.latitude, s.longitude]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 });
  } else if (!area && !proximityCenter) {
    map.setView(UK_CENTER, 6);
  }
}

async function loadProximityMap() {
  if (!proximityCenter) return;
  const { lat, lon } = proximityCenter;
  const radius = +document.getElementById('radius-slider').value;
  const type   = document.getElementById('map-type-filter').value;
  const params = new URLSearchParams({ lat, lon, radius });
  if (type) params.set('type', type);

  const suppliers = await apiFetch(`/api/map/near?${params}`);

  markersLayer.clearLayers();
  if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
  if (homeMarker)   { map.removeLayer(homeMarker);   homeMarker   = null; }

  radiusCircle = L.circle([lat, lon], {
    radius: radius * 1609.34,
    color: '#888', weight: 1.5, fillColor: '#888', fillOpacity: 0.04,
  }).addTo(map);
  map.fitBounds(radiusCircle.getBounds(), { padding: [4, 4] });

  homeMarker = L.circleMarker([lat, lon], {
    radius: 8, fillColor: '#111', color: '#fff', weight: 2, fillOpacity: 1,
  }).bindTooltip('Your location').addTo(map);

  suppliers.forEach(s => makeCircleMarker(s, true).addTo(markersLayer));
  setStatus(`${suppliers.length} suppliers within ${radius} miles`);
  renderResults(suppliers, true);
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

  document.getElementById('map-type-filter').addEventListener('change', () => {
    proximityCenter ? loadProximityMap() : loadMapSuppliers();
  });
  document.getElementById('map-area-filter').addEventListener('change', () => {
    if (proximityCenter) clearProximityState();
    loadMapSuppliers();
  });
}

async function searchPostcode() {
  const raw = document.getElementById('postcode-input').value.trim();
  if (!raw) return;

  setStatus('Looking up postcode…');
  const pc = raw.replace(/\s+/g, '');

  try {
    const res  = await fetch(`https://api.postcodes.io/postcodes/${pc}`);
    const data = await res.json();
    if (data.status !== 200) { setStatus('⚠️ Postcode not found.'); return; }

    proximityCenter = { lat: data.result.latitude, lon: data.result.longitude };
    document.getElementById('map-area-filter').value = '';
    map.setView([proximityCenter.lat, proximityCenter.lon], 10);
    document.getElementById('radius-row').style.display   = '';
    document.getElementById('postcode-clear').style.display = '';
    loadProximityMap();
  } catch {
    setStatus('⚠️ Could not reach postcode service.');
  }
}

function geolocate() {
  if (!navigator.geolocation) { setStatus('⚠️ Geolocation not supported.'); return; }
  const btn = document.getElementById('geolocate-btn');
  btn.textContent = '⏳ Locating…';
  btn.disabled = true;

  navigator.geolocation.getCurrentPosition(
    pos => {
      btn.textContent = '📍 My location';
      btn.disabled = false;
      proximityCenter = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      document.getElementById('postcode-input').value  = '';
      document.getElementById('map-area-filter').value = '';
      map.setView([proximityCenter.lat, proximityCenter.lon], 10);
      document.getElementById('radius-row').style.display    = '';
      document.getElementById('postcode-clear').style.display = '';
      loadProximityMap();
    },
    () => {
      btn.textContent = '📍 My location';
      btn.disabled = false;
      setStatus('⚠️ Could not get location — check browser permissions.');
    },
    { timeout: 10000 }
  );
}

function clearProximityState() {
  proximityCenter = null;
  document.getElementById('postcode-input').value          = '';
  document.getElementById('radius-row').style.display      = 'none';
  document.getElementById('postcode-clear').style.display  = 'none';
  if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
  if (homeMarker)   { map.removeLayer(homeMarker);   homeMarker   = null; }
}

function clearPostcode() {
  clearProximityState();
  map.setView(UK_CENTER, 6);
  loadMapSuppliers();
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
        loadMapSuppliers();
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
        loadMapSuppliers();
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
    } catch {
      msg.textContent = 'Something went wrong — please try again.';
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

// ── Area selects ──────────────────────────────────────────────────────────────
async function populateAreaSelects() {
  const areas = await apiFetch('/api/areas');
  const opts  = areas.map(a => `<option value="${esc(a)}">${esc(a)}</option>`).join('');
  document.getElementById('map-area-filter').insertAdjacentHTML('beforeend', opts);
  document.getElementById('add-areas').insertAdjacentHTML('beforeend', opts);
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
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}
