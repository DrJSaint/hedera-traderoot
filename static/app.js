/* Hedera TradeRoot — frontend */

const TYPE_COLOURS = {
  nursery:         '#2d9e4e',
  hard_landscaper: '#d23232',
  furniture:       '#4169e1',
  tools:           '#e07b00',
  lighting:        '#8a2be2',
  other:           '#888888',
};

const TYPE_LABELS = {
  nursery:         'Nursery',
  hard_landscaper: 'Hard Landscaper',
  furniture:       'Furniture',
  tools:           'Tools',
  lighting:        'Lighting',
  other:           'Other',
};

// ── State ─────────────────────────────────────────────────────────────────────
let map, markersLayer;
let proximityCenter = null;  // {lat, lon} when postcode active
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

      if (btn.dataset.tab === 'browse') loadBrowse();
      if (btn.dataset.tab === 'map') map.invalidateSize();
    });
  });
}

// ── Map ───────────────────────────────────────────────────────────────────────
function initMap() {
  map = L.map('map', { zoomControl: true }).setView([52.5, -1.5], 6);

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
  const rating = s.avg_rating ? `⭐ ${s.avg_rating}` : 'no reviews';
  const dist   = includeDistance && s.distance_miles != null
    ? `<br>📍 ${s.distance_miles} mi` : '';

  const marker = L.circleMarker([s.latitude, s.longitude], {
    radius: 7,
    fillColor: colour,
    color: '#fff',
    weight: 1.5,
    fillOpacity: 0.85,
  });

  marker.bindTooltip(`<b>${s.name}</b><br>${label}${dist}`, { sticky: true });
  marker.on('click', () => openDetail(s.id));
  return marker;
}

async function loadMapSuppliers() {
  const type   = document.getElementById('map-type-filter').value;
  const params = new URLSearchParams();
  if (type) params.set('type', type);

  const suppliers = await apiFetch(`/api/map?${params}`);
  markersLayer.clearLayers();
  suppliers.forEach(s => makeCircleMarker(s, false).addTo(markersLayer));
  setStatus('map', `${suppliers.length} suppliers on map`);
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
  if (radiusCircle)  { map.removeLayer(radiusCircle);  radiusCircle  = null; }
  if (homeMarker)    { map.removeLayer(homeMarker);    homeMarker    = null; }

  radiusCircle = L.circle([lat, lon], {
    radius: radius * 1609.34,
    color: '#888', weight: 1.5, fillColor: '#888', fillOpacity: 0.04,
  }).addTo(map);

  homeMarker = L.circleMarker([lat, lon], {
    radius: 8, fillColor: '#111', color: '#fff', weight: 2, fillOpacity: 1,
  }).bindTooltip('Your postcode').addTo(map);

  suppliers.forEach(s => makeCircleMarker(s, true).addTo(markersLayer));
  setStatus('map', `${suppliers.length} suppliers within ${radius} miles`);
  renderMapResults(suppliers);
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
}

async function searchPostcode() {
  const raw = document.getElementById('postcode-input').value.trim();
  if (!raw) return;

  setStatus('map', 'Looking up postcode…');
  const pc = raw.replace(/\s+/g, '');

  try {
    const res  = await fetch(`https://api.postcodes.io/postcodes/${pc}`);
    const data = await res.json();
    if (data.status !== 200) { setStatus('map', '⚠️ Postcode not found.'); return; }

    proximityCenter = { lat: data.result.latitude, lon: data.result.longitude };
    map.setView([proximityCenter.lat, proximityCenter.lon], 10);

    document.getElementById('radius-row').style.display = '';
    document.getElementById('postcode-clear').style.display = '';
    document.getElementById('map-results').style.display = '';

    loadProximityMap();
  } catch {
    setStatus('map', '⚠️ Could not reach postcode service.');
  }
}

function geolocate() {
  if (!navigator.geolocation) {
    setStatus('map', '⚠️ Geolocation is not supported by your browser.');
    return;
  }
  const btn = document.getElementById('geolocate-btn');
  btn.textContent = '⏳ Locating…';
  btn.disabled = true;

  navigator.geolocation.getCurrentPosition(
    pos => {
      btn.textContent = '📍 My location';
      btn.disabled = false;
      proximityCenter = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      document.getElementById('postcode-input').value = '';
      map.setView([proximityCenter.lat, proximityCenter.lon], 10);
      document.getElementById('radius-row').style.display = '';
      document.getElementById('postcode-clear').style.display = '';
      loadProximityMap();
    },
    err => {
      btn.textContent = '📍 My location';
      btn.disabled = false;
      setStatus('map', '⚠️ Could not get your location — check browser permissions.');
    },
    { timeout: 10000 }
  );
}

function clearPostcode() {
  proximityCenter = null;
  document.getElementById('postcode-input').value = '';
  document.getElementById('radius-row').style.display    = 'none';
  document.getElementById('postcode-clear').style.display = 'none';
  document.getElementById('map-results').innerHTML = '';
  if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
  if (homeMarker)   { map.removeLayer(homeMarker);   homeMarker   = null; }
  map.setView([52.5, -1.5], 6);
  loadMapSuppliers();
}

// ── Map results list ──────────────────────────────────────────────────────────
function renderMapResults(suppliers) {
  const el = document.getElementById('map-results');
  if (!suppliers.length) { el.innerHTML = '<p style="color:#888;padding:8px">No suppliers found.</p>'; return; }
  el.innerHTML = suppliers.map(s => supplierCardHTML(s, true)).join('');
  el.querySelectorAll('.supplier-card').forEach(card => {
    card.addEventListener('click', () => openDetail(+card.dataset.id));
  });
}

// ── Browse tab ────────────────────────────────────────────────────────────────
async function loadBrowse() {
  const area = document.getElementById('browse-area').value;
  const type = document.getElementById('browse-type').value;
  const params = new URLSearchParams();
  if (area) params.set('area', area);
  if (type) params.set('type', type);

  setStatus('browse', 'Loading…');
  const suppliers = await apiFetch(`/api/suppliers?${params}`);
  setStatus('browse', `${suppliers.length} supplier${suppliers.length !== 1 ? 's' : ''} found`);

  const el = document.getElementById('browse-results');
  if (!suppliers.length) { el.innerHTML = '<p style="color:#888;padding:8px">No suppliers found.</p>'; return; }
  el.innerHTML = suppliers.map(s => supplierCardHTML(s, false)).join('');
  el.querySelectorAll('.supplier-card').forEach(card => {
    card.addEventListener('click', () => openDetail(+card.dataset.id));
  });
}

// ── Supplier card HTML ────────────────────────────────────────────────────────
function supplierCardHTML(s, showDist) {
  const label   = TYPE_LABELS[s.type] || s.type;
  const badge   = `<span class="type-badge badge-${s.type}">${label}</span>`;
  const rating  = s.avg_rating ? `⭐ ${s.avg_rating} (${s.review_count})` : 'no reviews';
  const dist    = showDist && s.distance_miles != null ? ` · ${s.distance_miles} mi` : '';
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

  // deep link
  history.replaceState(null, '', `?supplier=${id}`);
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
  history.replaceState(null, '', '/');
}

function detailHTML(s, designers, allCats) {
  const label  = TYPE_LABELS[s.type] || s.type;
  const rating = s.avg_rating ? `⭐ ${s.avg_rating} (${s.review_count} reviews)` : 'No reviews yet';

  const living    = allCats.filter(c => c.group_name === 'Living');
  const nonliving = allCats.filter(c => c.group_name === 'Non-living');
  const assignedIds = new Set((s.categories || []).map(c => c.id));

  const catCheckboxes = (group) => group.map(c => `
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

  return `
    <h2>${esc(s.name)}</h2>
    <span class="type-badge badge-${s.type}">${label}</span>
    <div class="detail-row">⭐ ${rating}</div>
    ${s.phone   ? `<div class="detail-row">📞 <strong>${esc(s.phone)}</strong></div>` : ''}
    ${s.email   ? `<div class="detail-row">📧 ${esc(s.email)}</div>` : ''}
    ${s.website ? `<div class="detail-row">🌐 <a href="${esc(s.website)}" target="_blank" rel="noopener">${esc(s.website)}</a></div>` : ''}
    ${s.areas && s.areas.length ? `<div class="detail-row">📍 ${s.areas.map(esc).join(', ')}</div>` : ''}
    ${s.notes   ? `<div class="detail-row">📝 ${esc(s.notes)}</div>` : ''}

    ${allCats.length ? `
    <div class="modal-section">
      <h3>Categories</h3>
      <div id="cat-display">
        ${(s.categories||[]).length
          ? `<div class="category-chips">${s.categories.map(c=>`<span class="chip">${esc(c.name)}</span>`).join('')}</div>`
          : '<p style="font-size:13px;color:#888">None assigned.</p>'}
      </div>
      <details style="margin-top:8px">
        <summary style="font-size:13px;cursor:pointer;color:var(--green-mid)">Edit categories</summary>
        <div style="margin-top:8px">
          <div class="category-group"><h4>🌿 Living</h4>${catCheckboxes(living)}</div>
          <div class="category-group"><h4>🪨 Non-living</h4>${catCheckboxes(nonliving)}</div>
          <button class="btn-primary" id="save-cats-btn" style="margin-top:8px">Save</button>
          <p id="cat-msg" class="form-msg"></p>
        </div>
      </details>
    </div>` : ''}

    <div class="modal-section">
      <h3>Reviews</h3>
      <div id="reviews-container">${reviewsHTML}</div>
      ${designers.length ? `
      <details style="margin-top:12px">
        <summary style="font-size:13px;cursor:pointer;color:var(--green-mid)">✍️ Leave a review</summary>
        <div class="review-form" id="review-form">
          <label>Your name
            <select id="rev-designer">${designerOptions}</select>
          </label>
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
  // Save categories
  const saveCatsBtn = document.getElementById('save-cats-btn');
  if (saveCatsBtn) {
    saveCatsBtn.addEventListener('click', async () => {
      const ids = [...document.querySelectorAll('input[name="cat"]:checked')].map(el => +el.value);
      await apiFetch(`/api/suppliers/${s.id}/categories`, {
        method: 'PUT', body: JSON.stringify({ category_ids: ids }),
      });
      document.getElementById('cat-msg').textContent = 'Saved!';
      document.getElementById('cat-msg').className = 'form-msg success';
    });
  }

  // Submit review
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
      document.getElementById('rev-msg').className = 'form-msg success';
      // Refresh reviews
      const updated = await apiFetch(`/api/suppliers/${s.id}`);
      const reviewsHTML = (updated.reviews || []).map(r => `
        <div class="review-item">
          <div class="review-stars">${'⭐'.repeat(r.rating)}</div>
          <div>${esc(r.review_text)}</div>
          <div class="review-meta">${esc(r.designer)} · ${r.job_area || ''} · ${r.created_at.slice(0,10)}</div>
        </div>`).join('');
      document.getElementById('reviews-container').innerHTML = reviewsHTML;
    });
  }

  // Delete
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
    loadBrowse();
  });
}

// ── Add Supplier form ─────────────────────────────────────────────────────────
function initAddForm() {
  document.getElementById('add-form').addEventListener('submit', async e => {
    e.preventDefault();
    const fd   = new FormData(e.target);
    const areas = [...document.getElementById('add-areas').selectedOptions].map(o => o.value);
    const body = {
      name:       fd.get('name'),
      type:       fd.get('type'),
      website:    fd.get('website') || null,
      phone:      fd.get('phone')   || null,
      email:      fd.get('email')   || null,
      price_band: fd.get('price_band') || null,
      notes:      fd.get('notes')   || null,
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

  document.getElementById('browse-area').insertAdjacentHTML('beforeend', opts);
  document.getElementById('add-areas').insertAdjacentHTML('beforeend', opts);

  document.getElementById('browse-area').addEventListener('change', loadBrowse);
  document.getElementById('browse-type').addEventListener('change', loadBrowse);
}

// ── Deep link ─────────────────────────────────────────────────────────────────
function handleDeepLink() {
  const id = new URLSearchParams(location.search).get('supplier');
  if (id) openDetail(+id);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(tab, msg) {
  document.getElementById(`${tab}-status`).textContent = msg;
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
