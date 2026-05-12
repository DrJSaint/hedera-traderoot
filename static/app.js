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
  garden_designer:  '#3d6b99',
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
  garden_designer:  'Garden Designer',
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
let currentUser     = null;   // { authenticated, id, role, email, designer_id, name, company }
let welcomeMessage  = null;   // set after registration, consumed on first render

const FIELD_LABELS = {
  name:       'Business name',
  type:       'Type',
  trade:      'Trade supplier',
  website:    'Website',
  phone:      'Phone',
  email:      'Email',
  address:    'Address',
  postcode:   'Postcode',
  price_band: 'Price band',
  notes:      'Notes',
};

const NOTIF_ACK_KEY = 'traderoot:ack-requests';
function getAcknowledgedIds() {
  try { return new Set(JSON.parse(localStorage.getItem(NOTIF_ACK_KEY) || '[]')); }
  catch { return new Set(); }
}
function acknowledgeRequest(id) {
  const acked = getAcknowledgedIds();
  acked.add(id);
  localStorage.setItem(NOTIF_ACK_KEY, JSON.stringify([...acked]));
}

function setCountyHoverLabel(name = '') {
  const el = document.getElementById('county-hover-label');
  if (!el) return;
  el.textContent = name ?? '';
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await initAuth();
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
  const initCoords = suppliers.filter(s => s.latitude && s.longitude).map(s => [s.latitude, s.longitude]);
  if (initCoords.length) map.fitBounds(L.latLngBounds(initCoords), { padding: [40, 40], maxZoom: 11 });
  initAddForm();
  initRequestAddForm();
  initLoginForm();
  initRegisterForm();
  initForgotPasswordForm();
  initResetPasswordForm();
  initPasswordToggles();
  initModal();
  handleDeepLink();
});

// ── Auth ──────────────────────────────────────────────────────────────────────
async function initAuth() {
  try {
    const me = await apiFetch('/api/auth/me');
    currentUser = me.authenticated ? me : null;
  } catch {
    currentUser = null;
  }
  renderAuthUI();
  renderTabContent();
}

function renderAuthUI() {
  const el = document.getElementById('auth-area');
  if (!el) return;
  if (!currentUser) {
    el.innerHTML = '';
    return;
  }
  const roleLabel   = currentUser.role === 'admin' ? 'Admin' : 'Designer';
  const displayName = currentUser.name || currentUser.email || '';
  el.innerHTML = `
    <span class="auth-badge auth-badge--${currentUser.role}">${roleLabel}</span>
    <span class="auth-email">${esc(displayName)}</span>
    <button class="btn-ghost btn-ghost--dark" id="logout-btn">Logout</button>
  `;
  document.getElementById('logout-btn').addEventListener('click', doLogout);
}

async function doLogout() {
  await apiFetch('/api/auth/logout', { method: 'POST' });
  currentUser = null;
  renderAuthUI();
  renderTabContent();
  // Switch to account tab so they see the login form
  switchTab('account');
}

function renderTabContent() {
  // Add Supplier tab
  const addAnon     = document.getElementById('add-tab-anon');
  const addAdmin    = document.getElementById('add-tab-admin');
  const addDesigner = document.getElementById('add-tab-designer');
  if (addAnon && addAdmin && addDesigner) {
    addAnon.style.display     = !currentUser ? '' : 'none';
    addAdmin.style.display    = currentUser?.role === 'admin' ? '' : 'none';
    addDesigner.style.display = currentUser?.role === 'designer' ? '' : 'none';
  }

  // Account tab
  const accountAnon = document.getElementById('account-anon');
  const accountUser = document.getElementById('account-user');
  if (accountAnon && accountUser) {
    accountAnon.style.display = currentUser ? 'none' : '';
    accountUser.style.display = currentUser ? '' : 'none';
    if (currentUser) renderAccountContent();
  }
}

function renderAccountContent() {
  const el = document.getElementById('account-content');
  if (!el) return;

  if (currentUser.role === 'admin') {
    el.innerHTML = `
      <div class="account-header">
        <h2>Admin</h2>
        <p class="account-email">${esc(currentUser.email || '')}</p>
        <button class="btn-ghost" id="account-logout-btn">Logout</button>
      </div>
      <div class="modal-section">
        <h3>Pending Supplier Requests</h3>
        <div id="requests-list"><p style="color:#888;font-size:13px">Loading…</p></div>
      </div>`;
    document.getElementById('account-logout-btn').addEventListener('click', doLogout);
    loadAdminRequests();
  } else {
    const headerName = currentUser.name || currentUser.email || 'My Account';
    const welcome = welcomeMessage ? `<div class="welcome-banner">${welcomeMessage}</div>` : '';
    welcomeMessage = null;
    el.innerHTML = `
      <div class="account-header">
        <div>
          <h2>${esc(headerName)}</h2>
          ${currentUser.company ? `<p class="account-company">${esc(currentUser.company)}</p>` : ''}
          <p class="account-email">${esc(currentUser.email || '')}</p>
        </div>
        <button class="btn-ghost" id="account-logout-btn">Logout</button>
      </div>
      ${welcome}
      <div class="account-subtabs">
        <button class="account-subtab-btn active" data-subtab="profile">My Profile</button>
        <button class="account-subtab-btn" data-subtab="requests">My Requests</button>
      </div>
      <div id="account-subtab-profile" class="account-subtab-pane">
        ${renderProfileContent()}
      </div>
      <div id="account-subtab-requests" class="account-subtab-pane" style="display:none">
        <div id="requests-list"><p style="color:#888;font-size:13px">Loading…</p></div>
      </div>`;
    document.getElementById('account-logout-btn').addEventListener('click', doLogout);
    document.querySelectorAll('.account-subtab-btn').forEach(btn => {
      btn.addEventListener('click', () => switchAccountSubtab(btn.dataset.subtab));
    });
    wireProfileEvents();
    loadMyRequests();
  }
}

function switchAccountSubtab(name) {
  document.querySelectorAll('.account-subtab-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.subtab === name)
  );
  document.getElementById('account-subtab-profile').style.display = name === 'profile' ? '' : 'none';
  document.getElementById('account-subtab-requests').style.display = name === 'requests' ? '' : 'none';
}

function renderProfileContent() {
  return `
    <div class="profile-card" id="profile-view">
      <div class="profile-field">
        <span class="profile-label">Name</span>
        <span>${esc(currentUser.name || '—')}</span>
      </div>
      ${currentUser.company ? `<div class="profile-field"><span class="profile-label">Company</span><span>${esc(currentUser.company)}</span></div>` : ''}
      <div class="profile-field">
        <span class="profile-label">Email</span>
        <span>${esc(currentUser.email || '')}</span>
      </div>
      <button class="btn-ghost" id="edit-profile-btn" style="margin-top:12px">Edit profile</button>
    </div>
    <div id="profile-edit" style="display:none">
      <div class="edit-form" style="margin-top:12px">
        <label class="edit-label">Name<input id="profile-name" type="text" value="${esc(currentUser.name || '')}"></label>
        <label class="edit-label">Company<input id="profile-company" type="text" value="${esc(currentUser.company || '')}"></label>
        <div class="edit-actions">
          <button class="btn-primary" id="save-profile-btn">Save</button>
          <button class="btn-ghost" id="cancel-profile-btn">Cancel</button>
        </div>
        <p id="profile-msg" class="form-msg"></p>
      </div>
    </div>`;
}

function wireProfileEvents() {
  const editBtn = document.getElementById('edit-profile-btn');
  if (!editBtn) return;
  editBtn.addEventListener('click', () => {
    document.getElementById('profile-view').style.display = 'none';
    document.getElementById('profile-edit').style.display = '';
  });
  document.getElementById('cancel-profile-btn')?.addEventListener('click', () => {
    document.getElementById('profile-view').style.display = '';
    document.getElementById('profile-edit').style.display = 'none';
  });
  document.getElementById('save-profile-btn')?.addEventListener('click', async () => {
    const name    = document.getElementById('profile-name').value.trim();
    const company = document.getElementById('profile-company').value.trim();
    const msg     = document.getElementById('profile-msg');
    try {
      await apiFetch('/api/auth/profile', {
        method: 'PATCH',
        body: JSON.stringify({ name, company: company || null }),
      });
      currentUser.name    = name;
      currentUser.company = company || null;
      renderAuthUI();
      renderAccountContent();
    } catch (err) {
      msg.textContent = err.detail || 'Could not save — try again.';
      msg.className   = 'form-msg error';
    }
  });
}

async function loadAdminRequests() {
  const list = await apiFetch('/api/requests');
  renderRequestsList(list, true);
}

async function loadMyRequests() {
  const allRequests = await apiFetch('/api/requests');
  const el = document.getElementById('requests-list');
  if (!el) return;

  const pending = allRequests.filter(r => r.status === 'pending');
  const past    = allRequests.filter(r => r.status !== 'pending');
  const acked   = getAcknowledgedIds();
  const unacked = past.filter(r => !acked.has(r.id));

  let html = '';

  if (unacked.length) {
    unacked.forEach(r => {
      const isApproved   = r.status === 'approved';
      let supplierName;
      try { supplierName = r.target_supplier_name || JSON.parse(r.payload || '{}').name || 'supplier'; }
      catch { supplierName = 'supplier'; }
      const noteText = !isApproved && r.reviewer_notes ? ` — "${esc(r.reviewer_notes)}"` : '';
      html += `<div class="notif-banner notif-banner--${r.status}">
        <strong>${isApproved ? '✓ Approved' : '✗ Rejected'}</strong>:
        Your request for <em>${esc(supplierName)}</em> has been ${r.status}${noteText}.
        <button class="notif-dismiss" data-id="${r.id}">Dismiss ✕</button>
      </div>`;
    });
  }

  if (pending.length) {
    html += `<div class="requests-section-header">Pending requests</div>`;
    html += pending.map(r => requestItemHTML(r, false)).join('');
  } else {
    html += `<p style="color:#888;font-size:13px;padding:8px 0">No pending requests.</p>`;
  }

  if (past.length) {
    html += `<details class="past-requests-details">
      <summary>Past requests (${past.length})</summary>
      ${past.map(r => pastRequestItemHTML(r)).join('')}
    </details>`;
  }

  el.innerHTML = html;

  el.querySelectorAll('.notif-dismiss').forEach(btn => {
    btn.addEventListener('click', () => {
      acknowledgeRequest(+btn.dataset.id);
      btn.closest('.notif-banner').remove();
    });
  });
  el.querySelectorAll('.request-cancel-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await apiFetch(`/api/requests/${btn.dataset.id}`, { method: 'DELETE' });
      loadMyRequests();
    });
  });
}

function renderRequestsList(requests, isAdmin) {
  const el = document.getElementById('requests-list');
  if (!el) return;
  if (!requests.length) {
    el.innerHTML = '<p style="color:#888;font-size:13px">No pending requests.</p>';
    return;
  }
  el.innerHTML = requests.map(r => requestItemHTML(r, isAdmin)).join('');
  el.querySelectorAll('.request-approve-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const result = await apiFetch(`/api/requests/${btn.dataset.id}/review`, {
        method: 'PATCH',
        body: JSON.stringify({ decision: 'approved' }),
      });
      await refreshSuppliers();
      loadAdminRequests();
      if (result?.geocode_failed) {
        showGeocodeWarning(result.supplier_id);
      }
    });
  });
  el.querySelectorAll('.request-reject-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const notes = prompt('Reason for rejection (optional):') || null;
      await apiFetch(`/api/requests/${btn.dataset.id}/review`, {
        method: 'PATCH',
        body: JSON.stringify({ decision: 'rejected', reviewer_notes: notes }),
      });
      await refreshSuppliers();
      loadAdminRequests();
    });
  });
}

function showGeocodeWarning(supplierId) {
  const existing = document.getElementById('geocode-warn-banner');
  if (existing) existing.remove();
  const banner = document.createElement('div');
  banner.id = 'geocode-warn-banner';
  banner.className = 'geocode-warn-banner';
  banner.innerHTML = `⚠️ Supplier added but no map pin — address could not be geocoded.
    <a href="#" class="geocode-warn-banner__link">Edit the supplier</a> to fix it.
    <button class="geocode-warn-banner__close">✕</button>`;
  banner.querySelector('.geocode-warn-banner__link').addEventListener('click', e => {
    e.preventDefault();
    banner.remove();
    openSupplierDetail(supplierId);
  });
  banner.querySelector('.geocode-warn-banner__close').addEventListener('click', () => banner.remove());
  document.body.prepend(banner);
}

function requestItemHTML(r, isAdmin) {
  const payload = (() => { try { return JSON.parse(r.payload); } catch { return {}; } })();
  const supplierName = r.target_supplier_name || payload.name || '(new supplier)';
  const typeLabel = r.request_type === 'add' ? 'New supplier' : 'Edit';
  const date = (r.updated_at || r.created_at || '').slice(0, 10);
  const changes = Object.entries(payload)
    .filter(([k]) => k !== 'areas')
    .map(([k, v]) => {
      const label = FIELD_LABELS[k] || k;
      let display = String(v ?? '');
      if (k === 'trade') display = v ? 'Yes' : 'No';
      if (k === 'category_ids') display = Array.isArray(v) ? `${v.length} selected` : display;
      return `<span class="request-field"><span class="request-field__label">${esc(label)}</span>: <strong>${esc(display)}</strong></span>`;
    }).join('');

  return `
    <div class="request-item">
      <div class="request-item__header">
        <span class="request-type-badge request-type--${r.request_type}">${typeLabel}</span>
        <span class="request-supplier">${esc(supplierName)}</span>
        <span class="request-date">${date}</span>
      </div>
      ${isAdmin ? `<div class="request-item__from">from ${esc(r.requester_email || '')}</div>` : ''}
      <div class="request-item__changes">${changes || '<span style="color:#888;font-size:12px">No field changes</span>'}</div>
      <div class="request-item__actions">
        ${isAdmin ? `
          <button class="btn-primary request-approve-btn" data-id="${r.id}" style="font-size:12px;padding:5px 12px">Approve</button>
          <button class="btn-ghost request-reject-btn" data-id="${r.id}" style="font-size:12px;padding:5px 12px">Reject</button>
        ` : `
          <button class="btn-ghost request-cancel-btn" data-id="${r.id}" style="font-size:12px;padding:5px 12px">Cancel request</button>
        `}
      </div>
    </div>`;
}

function pastRequestItemHTML(r) {
  const payload = (() => { try { return JSON.parse(r.payload); } catch { return {}; } })();
  const supplierName = r.target_supplier_name || payload.name || '(new supplier)';
  const typeLabel = r.request_type === 'add' ? 'New supplier' : 'Edit';
  const date = (r.reviewed_at || r.updated_at || r.created_at || '').slice(0, 10);
  const statusMap   = { approved: '✓ Approved', rejected: '✗ Rejected', cancelled: 'Cancelled' };
  const statusClass = { approved: 'status--approved', rejected: 'status--rejected', cancelled: 'status--cancelled' };
  const changes = Object.entries(payload)
    .filter(([k]) => k !== 'areas')
    .map(([k, v]) => {
      const label = FIELD_LABELS[k] || k;
      let display = String(v ?? '');
      if (k === 'trade') display = v ? 'Yes' : 'No';
      if (k === 'category_ids') display = Array.isArray(v) ? `${v.length} selected` : display;
      return `<span class="request-field"><span class="request-field__label">${esc(label)}</span>: <strong>${esc(display)}</strong></span>`;
    }).join('');
  return `
    <div class="request-item request-item--past">
      <div class="request-item__header">
        <span class="request-type-badge request-type--${r.request_type}">${typeLabel}</span>
        <span class="request-supplier">${esc(supplierName)}</span>
        <span class="request-date">${date}</span>
        <span class="request-status ${statusClass[r.status] || ''}">${statusMap[r.status] || r.status}</span>
      </div>
      <div class="request-item__changes">${changes || '<span style="color:#888;font-size:12px">No field changes</span>'}</div>
      ${r.reviewer_notes ? `<div class="request-reviewer-notes">Admin note: "${esc(r.reviewer_notes)}"</div>` : ''}
    </div>`;
}

// ── Auth forms ────────────────────────────────────────────────────────────────
function initLoginForm() {
  // Auth switcher (login / register tabs within Account tab)
  document.querySelectorAll('.auth-switch-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.auth-switch-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.auth-pane').forEach(p => p.style.display = 'none');
      document.getElementById(`auth-${btn.dataset.pane}-pane`).style.display = '';
    });
  });

  document.getElementById('login-form').addEventListener('submit', async e => {
    e.preventDefault();
    const fd  = new FormData(e.target);
    const msg = document.getElementById('login-msg');
    try {
      const result = await apiFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: fd.get('email'), password: fd.get('password') }),
      });
      currentUser = { authenticated: true, ...result };
      // Re-fetch full me to get email + designer_id
      const me = await apiFetch('/api/auth/me');
      currentUser = me;
      renderAuthUI();
      renderTabContent();
      e.target.reset();
    } catch (err) {
      msg.textContent = err.detail || 'Login failed — check your email and password.';
      msg.className   = 'form-msg error';
    }
  });
}

function initRegisterForm() {
  document.getElementById('register-form').addEventListener('submit', async e => {
    e.preventDefault();
    const fd  = new FormData(e.target);
    const msg = document.getElementById('register-msg');
    try {
      const result = await apiFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          name:     fd.get('name'),
          email:    fd.get('email'),
          password: fd.get('password'),
          company:  fd.get('company') || null,
        }),
      });
      currentUser = { authenticated: true, ...result };
      const me = await apiFetch('/api/auth/me');
      currentUser = me;
      renderAuthUI();
      renderTabContent();  // shows account-user pane, renders content once without welcome
      welcomeMessage = `Welcome, ${esc(me.name || fd.get('name') || '')}! Your account is ready.`;
      switchTab('account'); // re-renders account content WITH welcome banner
      e.target.reset();
    } catch (err) {
      msg.textContent = err.status === 409 ? 'That email is already registered.' : (err.detail || 'Registration failed.');
      msg.className   = 'form-msg error';
    }
  });
}

function initPasswordToggles() {
  document.addEventListener('click', e => {
    const btn = e.target.closest('.password-toggle');
    if (!btn) return;
    const input = btn.closest('.password-field').querySelector('input');
    const showing = input.type === 'text';
    input.type = showing ? 'password' : 'text';
    btn.textContent = showing ? '👁' : '🙈';
    btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
  });
}

function initForgotPasswordForm() {
  document.getElementById('forgot-password-link').addEventListener('click', () => {
    document.querySelectorAll('.auth-pane').forEach(p => p.style.display = 'none');
    document.getElementById('auth-forgot-pane').style.display = '';
  });

  document.getElementById('back-to-login-link').addEventListener('click', () => {
    document.querySelectorAll('.auth-pane').forEach(p => p.style.display = 'none');
    document.getElementById('auth-login-pane').style.display = '';
  });

  document.getElementById('forgot-form').addEventListener('submit', async e => {
    e.preventDefault();
    const fd  = new FormData(e.target);
    const msg = document.getElementById('forgot-msg');
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      await apiFetch('/api/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email: fd.get('email') }),
      });
      msg.textContent = 'If that email is registered, a reset link is on its way.';
      msg.className   = 'form-msg success';
      e.target.reset();
    } catch (err) {
      msg.textContent = err.detail || 'Something went wrong — please try again.';
      msg.className   = 'form-msg error';
    } finally {
      btn.disabled = false;
    }
  });
}

function initResetPasswordForm() {
  const params     = new URLSearchParams(window.location.search);
  const resetToken = params.get('reset_token');
  if (resetToken) {
    switchTab('account');
    document.querySelectorAll('.auth-pane').forEach(p => p.style.display = 'none');
    document.getElementById('auth-reset-pane').style.display = '';
  }

  document.getElementById('reset-form').addEventListener('submit', async e => {
    e.preventDefault();
    const fd  = new FormData(e.target);
    const msg = document.getElementById('reset-msg');

    if (fd.get('password') !== fd.get('confirm')) {
      msg.textContent = 'Passwords do not match.';
      msg.className   = 'form-msg error';
      return;
    }

    const token = new URLSearchParams(window.location.search).get('reset_token');
    if (!token) {
      msg.textContent = 'Reset link is missing — please use the link from your email.';
      msg.className   = 'form-msg error';
      return;
    }

    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      await apiFetch('/api/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, password: fd.get('password') }),
      });
      msg.textContent = 'Password updated — you can now log in.';
      msg.className   = 'form-msg success';
      e.target.reset();
      // Clean token from URL and show login pane after a moment
      history.replaceState(null, '', window.location.pathname);
      setTimeout(() => {
        document.querySelectorAll('.auth-pane').forEach(p => p.style.display = 'none');
        document.getElementById('auth-login-pane').style.display = '';
      }, 2000);
    } catch (err) {
      msg.textContent = err.detail || 'Reset failed — the link may have expired.';
      msg.className   = 'form-msg error';
    } finally {
      btn.disabled = false;
    }
  });
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

function switchTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabName);
  });
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + tabName).classList.add('active');
  if (tabName === 'map') map.invalidateSize();
  if (tabName === 'account' && currentUser) renderAccountContent();
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
    if (!showBorders) map.removeLayer(countyBoundsLayer);
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

function getPopulatedAreas(suppliers) {
  const names = new Set();
  suppliers.forEach(s => (s.areas || []).forEach(a => names.add(a)));
  return [...names].sort((a, b) => a.localeCompare(b));
}

function populateAreaOptions(suppliers, allAreas) {
  const addAreasEl     = document.getElementById('add-areas');
  const requestAreaEl  = document.getElementById('request-area');
  const mapAreaFilterEl = document.getElementById('map-area-filter');

  allAreas.forEach(name => {
    if (addAreasEl)    addAreasEl.appendChild(new Option(name, name));
    if (requestAreaEl) requestAreaEl.appendChild(new Option(name, name));
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
  document.getElementById('trade-filter-yes').addEventListener('change', e => {
    showTrade = e.target.checked; applyFilters();
  });
  document.getElementById('trade-filter-no').addEventListener('change', e => {
    showNonTrade = e.target.checked; applyFilters();
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
  } catch { /* leave view unchanged */ }
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
  } else if (!proximityRaw && !areaVal && searchQuery && list.length) {
    const coords = list.filter(s => s.latitude && s.longitude).map(s => [s.latitude, s.longitude]);
    if (coords.length) {
      const bounds = L.latLngBounds(coords);
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
    }
  } else if (!proximityRaw && !areaVal && !searchQuery) {
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

  if (document.body.dataset.proximityRequestKey !== requestKey) return;
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
    document.getElementById('radius-row').style.display    = '';
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
    if (!Number.isFinite(cached.lat) || !Number.isFinite(cached.lon) || ageMs > GEOLOCATION_CACHE_MAX_AGE_MS) return null;
    return cached;
  } catch { return null; }
}

function writeCachedLocation(coords) {
  try {
    localStorage.setItem(GEOLOCATION_CACHE_KEY, JSON.stringify({
      lat: coords.latitude, lon: coords.longitude,
      accuracy: coords.accuracy ?? null, timestamp: Date.now(),
    }));
  } catch { /* ignore */ }
}

function applyProximityCenter(lat, lon) {
  proximityCenter = { lat, lon };
  document.getElementById('postcode-input').value = '';
  map.setView([lat, lon], 10);
  document.getElementById('radius-row').style.display    = '';
  document.getElementById('postcode-clear').style.display = '';
  loadProximityMap();
}

function geolocate() {
  if (!window.isSecureContext) { setStatus('⚠️ Location requires HTTPS on mobile browsers.'); return; }
  if (!navigator.geolocation)  { setStatus('⚠️ Geolocation not supported.'); return; }
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

  const getPosition = options => new Promise((resolve, reject) =>
    navigator.geolocation.getCurrentPosition(resolve, reject, options)
  );

  getPosition({ maximumAge: 300000, timeout: 1500, enableHighAccuracy: false })
    .catch(() => {
      if (!hasAppliedCachedLocation) setStatus('Still locating… trying more precise fix.');
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
      if (!hasAppliedCachedLocation) setStatus('⚠️ Could not get location — check browser permissions.');
    });
}

function clearProximityState() {
  if (proximityAbortController) { proximityAbortController.abort(); proximityAbortController = null; }
  delete document.body.dataset.proximityRequestKey;
  proximityRaw    = null;
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

  const fetches = [
    apiFetch(`/api/suppliers/${id}`),
    apiFetch('/api/categories'),
  ];
  if (currentUser?.role === 'designer') {
    fetches.push(apiFetch('/api/requests'));
  }

  const [s, allCats, myRequests] = await Promise.all(fetches);
  const pendingRequest = (myRequests || []).find(
    r => r.target_supplier_id === id && r.status === 'pending'
  ) || null;

  renderDetailView(s, allCats, pendingRequest);
  history.replaceState(null, '', `?supplier=${id}`);
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
  history.replaceState(null, '', '/');
}

// ── Detail view (read-only) ───────────────────────────────────────────────────
function renderDetailView(s, allCats, pendingRequest) {
  document.getElementById('modal-body').innerHTML = detailViewHTML(s, allCats, pendingRequest);
  wireDetailViewEvents(s, allCats, pendingRequest);
}

function detailViewHTML(s, allCats, pendingRequest) {
  const label    = TYPE_LABELS[s.type] || s.type;
  const rating   = s.avg_rating ? `⭐ ${s.avg_rating} (${s.review_count} reviews)` : 'No reviews yet';
  const tradeBadge = s.trade
    ? `<span class="trade-status-badge trade-status--yes">Trade</span>`
    : `<span class="trade-status-badge trade-status--no">Non-trade</span>`;

  const primary   = s.primary_area;
  const secondary = (s.areas || []).filter(a => a !== primary);
  const areaStr   = primary
    ? `📍 <strong>${esc(primary)}</strong>${secondary.length ? ` <span style="color:#888;font-size:0.88em">(also: ${secondary.map(esc).join(', ')})</span>` : ''}`
    : s.areas?.length ? `📍 ${s.areas.map(esc).join(', ')}` : '';

  const assignedCats = s.categories || [];
  const living    = assignedCats.filter(c => c.group_name === 'Living');
  const nonliving = assignedCats.filter(c => c.group_name === 'Non-living');
  const catsHTML  = assignedCats.length
    ? `${living.length    ? `<div class="category-group"><h4>🌿 Living</h4><div class="category-chips">${living.map(c => `<span class="chip">${esc(c.name)}</span>`).join('')}</div></div>` : ''}
       ${nonliving.length ? `<div class="category-group"><h4>🪨 Non-living</h4><div class="category-chips">${nonliving.map(c => `<span class="chip">${esc(c.name)}</span>`).join('')}</div></div>` : ''}`
    : '<p style="font-size:13px;color:#888">No categories assigned.</p>';

  const reviewsHTML = (s.reviews || []).length
    ? s.reviews.map(r => `
        <div class="review-item">
          <div class="review-stars">${'⭐'.repeat(r.rating)}</div>
          <div>${esc(r.review_text)}</div>
          <div class="review-meta">${esc(r.designer)}${r.designer_company ? ' · ' + esc(r.designer_company) : ''} · ${r.created_at.slice(0,10)}</div>
        </div>`).join('')
    : '<p style="font-size:13px;color:#888">No reviews yet.</p>';

  const hasDirectionsTarget = (Number.isFinite(s.latitude) && Number.isFinite(s.longitude)) || !!s.address;

  const canEdit   = !!currentUser;
  const isAdmin   = currentUser?.role === 'admin';

  const pendingBanner = pendingRequest
    ? `<div class="pending-banner">You have a pending edit request for this supplier. <button class="pending-banner__edit" id="banner-edit-btn">Update or cancel it</button></div>`
    : '';

  const editBtn = canEdit
    ? `<button class="btn-ghost detail-edit-btn" id="edit-btn">${pendingRequest ? 'Update request' : (isAdmin ? 'Edit' : 'Suggest edit')}</button>`
    : '';

  const myReview = currentUser?.designer_id
    ? (s.reviews || []).find(r => r.designer_id === currentUser.designer_id)
    : null;

  const reviewForm = !currentUser
    ? '<p style="font-size:12px;color:#888;margin-top:8px">Log in to leave a review.</p>'
    : myReview
    ? `<div class="review-form" id="my-review-view">
        <p style="font-size:13px;color:#888;margin:0 0 6px">Your review:</p>
        <div class="review-stars">${'⭐'.repeat(myReview.rating)}</div>
        <div style="font-size:14px;margin:4px 0">${esc(myReview.review_text)}</div>
        <div style="margin-top:8px;display:flex;gap:8px">
          <button class="btn-ghost" id="edit-review-btn" style="font-size:12px;padding:4px 10px">Edit</button>
          <button class="btn-ghost" id="delete-review-btn" style="font-size:12px;padding:4px 10px;color:#c0392b">Delete</button>
        </div>
        <p id="rev-msg" class="form-msg"></p>
      </div>
      <div class="review-form" id="my-review-edit" style="display:none">
        <label>Rating
          <select id="rev-rating">
            <option value="5">⭐⭐⭐⭐⭐</option>
            <option value="4">⭐⭐⭐⭐</option>
            <option value="3">⭐⭐⭐</option>
            <option value="2">⭐⭐</option>
            <option value="1">⭐</option>
          </select>
        </label>
        <label>Review<textarea id="rev-text" rows="3">${esc(myReview.review_text)}</textarea></label>
        <button class="btn-primary" id="submit-review-btn">Save changes</button>
        <button class="btn-ghost" id="cancel-edit-review-btn" style="margin-left:8px">Cancel</button>
        <p id="rev-msg-edit" class="form-msg"></p>
      </div>`
    : `<details style="margin-top:12px">
        <summary style="font-size:13px;cursor:pointer;color:var(--green-mid)">✍️ Leave a review</summary>
        <div class="review-form">
          <label>Rating
            <select id="rev-rating">
              <option value="5">⭐⭐⭐⭐⭐</option>
              <option value="4">⭐⭐⭐⭐</option>
              <option value="3" selected>⭐⭐⭐</option>
              <option value="2">⭐⭐</option>
              <option value="1">⭐</option>
            </select>
          </label>
          <label>Review<textarea id="rev-text" rows="3" placeholder="Your experience…"></textarea></label>
          <button class="btn-primary" id="submit-review-btn">Submit</button>
          <p id="rev-msg" class="form-msg"></p>
        </div>
      </details>`;

  return `
    <div class="detail-title-row">
      <div>
        <h2>${esc(s.name)}</h2>
        <span class="type-badge badge-${s.type}">${label}</span>
        ${tradeBadge}
      </div>
      ${editBtn}
    </div>

    ${pendingBanner}

    <div class="detail-row">${rating}</div>
    ${s.phone   ? `<div class="detail-row">📞 <strong>${esc(s.phone)}</strong></div>` : ''}
    ${s.email   ? `<div class="detail-row">📧 ${esc(s.email)}</div>` : ''}
    ${s.website ? `<div class="detail-row">🌐 <a href="${esc(s.website)}" target="_blank" rel="noopener">${esc(s.website)}</a></div>` : ''}
    ${s.address ? `<div class="detail-row">🧭 ${esc(s.address)}</div>` : ''}
    ${hasDirectionsTarget ? `<div class="detail-row"><button class="btn-primary" id="directions-btn" type="button">Directions</button><span id="directions-msg" class="form-msg" style="font-size:12px;margin-left:8px"></span></div>` : ''}
    ${areaStr   ? `<div class="detail-row">${areaStr}</div>` : ''}
    ${s.notes   ? `<div class="detail-row">📝 ${esc(s.notes)}</div>` : ''}

    <div class="modal-section">
      <h3>Categories</h3>
      ${catsHTML}
    </div>

    <div class="modal-section">
      <h3>Reviews</h3>
      <div id="reviews-container">${reviewsHTML}</div>
      ${reviewForm}
    </div>

    ${isAdmin ? `
    <div class="modal-section">
      <button class="btn-danger" id="delete-btn">Delete supplier</button>
      <div id="delete-confirm" style="display:none;margin-top:8px">
        <p style="font-size:13px;color:#c0392b;margin-bottom:8px">Are you sure? This cannot be undone.</p>
        <button class="btn-danger" id="delete-confirm-btn">Yes, delete</button>
        <button class="btn-ghost" id="delete-cancel-btn" style="margin-left:8px">Cancel</button>
      </div>
    </div>` : ''}`;
}

function wireDetailViewEvents(s, allCats, pendingRequest) {
  const directionsBtn = document.getElementById('directions-btn');
  if (directionsBtn) directionsBtn.addEventListener('click', () => openDirections(s));

  const editBtn = document.getElementById('edit-btn');
  if (editBtn) {
    editBtn.addEventListener('click', () => enterEditMode(s, allCats, pendingRequest));
  }
  const bannerEditBtn = document.getElementById('banner-edit-btn');
  if (bannerEditBtn) {
    bannerEditBtn.addEventListener('click', () => enterEditMode(s, allCats, pendingRequest));
  }

  const submitRevBtn = document.getElementById('submit-review-btn');
  if (submitRevBtn) {
    // Set correct rating in edit form if user already has a review
    const myReview = currentUser?.designer_id
      ? (s.reviews || []).find(r => r.designer_id === currentUser.designer_id)
      : null;
    if (myReview) {
      const ratingEl = document.getElementById('rev-rating');
      if (ratingEl) ratingEl.value = String(myReview.rating);
    }

    const isEdit = !!myReview;
    submitRevBtn.addEventListener('click', async () => {
      const msgId = isEdit ? 'rev-msg-edit' : 'rev-msg';
      const text = document.getElementById('rev-text').value.trim();
      if (!text) { document.getElementById(msgId).textContent = 'Please write a review.'; return; }
      submitRevBtn.disabled = true;
      try {
        await apiFetch(`/api/suppliers/${s.id}/reviews${isEdit ? '/mine' : ''}`, {
          method: isEdit ? 'PATCH' : 'POST',
          body: JSON.stringify({
            rating:      +document.getElementById('rev-rating').value,
            review_text: text,
          }),
        });
        await refreshSuppliers();
        openDetail(s.id);
      } catch (err) {
        const msg = document.getElementById(msgId);
        msg.textContent = err.detail || 'Something went wrong.';
        msg.className   = 'form-msg error';
      } finally {
        submitRevBtn.disabled = false;
      }
    });
  }

  const editRevBtn = document.getElementById('edit-review-btn');
  if (editRevBtn) {
    editRevBtn.addEventListener('click', () => {
      document.getElementById('my-review-view').style.display = 'none';
      document.getElementById('my-review-edit').style.display = '';
    });
  }

  const cancelEditRevBtn = document.getElementById('cancel-edit-review-btn');
  if (cancelEditRevBtn) {
    cancelEditRevBtn.addEventListener('click', () => {
      document.getElementById('my-review-edit').style.display = 'none';
      document.getElementById('my-review-view').style.display = '';
    });
  }

  const deleteRevBtn = document.getElementById('delete-review-btn');
  if (deleteRevBtn) {
    deleteRevBtn.addEventListener('click', async () => {
      deleteRevBtn.disabled = true;
      try {
        await apiFetch(`/api/suppliers/${s.id}/reviews/mine`, { method: 'DELETE' });
        await refreshSuppliers();
        openDetail(s.id);
      } catch (err) {
        const msg = document.getElementById('rev-msg');
        msg.textContent = err.detail || 'Delete failed.';
        msg.className   = 'form-msg error';
        deleteRevBtn.disabled = false;
      }
    });
  }

  const deleteBtn = document.getElementById('delete-btn');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', () => {
      document.getElementById('delete-confirm').style.display = '';
    });
    document.getElementById('delete-cancel-btn').addEventListener('click', () => {
      document.getElementById('delete-confirm').style.display = 'none';
    });
    document.getElementById('delete-confirm-btn').addEventListener('click', async () => {
      await apiFetch(`/api/suppliers/${s.id}`, { method: 'DELETE' });
      closeModal();
      refreshSuppliers();
    });
  }
}

// ── Detail edit mode ──────────────────────────────────────────────────────────
function enterEditMode(s, allCats, pendingRequest) {
  const isAdmin = currentUser?.role === 'admin';
  // If designer has a pending request, pre-fill form with pending payload
  const pendingPayload = pendingRequest
    ? (() => { try { return JSON.parse(pendingRequest.payload); } catch { return {}; } })()
    : {};
  const vals = isAdmin ? s : { ...s, ...pendingPayload };

  document.getElementById('modal-body').innerHTML = detailEditHTML(vals, allCats, isAdmin, !!pendingRequest);
  wireDetailEditEvents(s, allCats, isAdmin, pendingRequest);
}

function detailEditHTML(vals, allCats, isAdmin, hasPending) {
  const living    = allCats.filter(c => c.group_name === 'Living');
  const nonliving = allCats.filter(c => c.group_name === 'Non-living');
  const assignedIds = new Set((vals.categories || []).map(c => c.id));

  const catCheckboxes = group =>
    `<div class="cat-checkbox-group">${group.map(c => `
      <label class="cat-checkbox">
        <input type="checkbox" name="cat" value="${c.id}" ${assignedIds.has(c.id) ? 'checked' : ''}>
        ${esc(c.name)}
      </label>`).join('')}</div>`;

  const typeOptions = Object.entries(TYPE_LABELS).map(([v, t]) =>
    `<option value="${v}" ${vals.type === v ? 'selected' : ''}>${t}</option>`
  ).join('');

  const pendingNotice = hasPending
    ? `<div class="pending-banner pending-banner--edit">Updating your pending request — changes are not live until approved.</div>`
    : '';

  const saveLabel = isAdmin ? 'Save' : (hasPending ? 'Update request' : 'Submit request');

  return `
    <div class="detail-edit-header">
      <h2>${isAdmin ? 'Edit Supplier' : 'Suggest Edit'}</h2>
    </div>
    ${pendingNotice}
    <div class="edit-form">
      <label class="edit-label">Business name<input id="edit-name" type="text" value="${esc(vals.name || '')}"></label>
      <label class="edit-label">Type<select id="edit-type">${typeOptions}</select></label>
      <label class="edit-label edit-label--inline">
        <input type="checkbox" id="edit-trade" ${vals.trade ? 'checked' : ''}> Trade supplier
      </label>
      <label class="edit-label">Website<input id="edit-website" type="url" value="${esc(vals.website || '')}"></label>
      <label class="edit-label">Phone<input id="edit-phone" type="tel" value="${esc(vals.phone || '')}"></label>
      <label class="edit-label">Email<input id="edit-email" type="email" value="${esc(vals.email || '')}"></label>
      <label class="edit-label">Address<input id="edit-address" type="text" value="${esc(vals.address || '')}"></label>
      <label class="edit-label">Price band
        <select id="edit-price-band">
          <option value="" ${!vals.price_band ? 'selected' : ''}>—</option>
          <option value="budget"  ${vals.price_band === 'budget'  ? 'selected' : ''}>Budget</option>
          <option value="mid"     ${vals.price_band === 'mid'     ? 'selected' : ''}>Mid</option>
          <option value="premium" ${vals.price_band === 'premium' ? 'selected' : ''}>Premium</option>
        </select>
      </label>
      <label class="edit-label">Notes<textarea id="edit-notes" rows="3">${esc(vals.notes || '')}</textarea></label>

      ${allCats.length ? `
      <div class="modal-section">
        <h3>Categories</h3>
        ${!isAdmin ? `<p style="font-size:12px;color:var(--text-muted);margin-bottom:8px">Category changes will be reviewed by an admin before going live.</p>` : ''}
        <div class="category-group"><h4>🌿 Living</h4>${catCheckboxes(living)}</div>
        <div class="category-group"><h4>🪨 Non-living</h4>${catCheckboxes(nonliving)}</div>
      </div>` : ''}

      <div class="edit-actions">
        <button class="btn-primary" id="save-edit-btn">${saveLabel}</button>
        <button class="btn-ghost"   id="cancel-edit-btn">Cancel</button>
        ${!isAdmin && hasPending ? `<button class="btn-danger" id="cancel-request-btn" style="margin-left:auto">Cancel pending request</button>` : ''}
      </div>
      <p id="edit-msg" class="form-msg"></p>
    </div>`;
}

function wireDetailEditEvents(s, allCats, isAdmin, pendingRequest) {
  document.getElementById('cancel-edit-btn').addEventListener('click', async () => {
    // Reload fresh supplier data before returning to view
    const [fresh, freshCats] = await Promise.all([
      apiFetch(`/api/suppliers/${s.id}`),
      apiFetch('/api/categories'),
    ]);
    renderDetailView(fresh, freshCats, null);
  });

  const cancelRequestBtn = document.getElementById('cancel-request-btn');
  if (cancelRequestBtn && pendingRequest) {
    cancelRequestBtn.addEventListener('click', async () => {
      await apiFetch(`/api/requests/${pendingRequest.id}`, { method: 'DELETE' });
      const [fresh, freshCats] = await Promise.all([
        apiFetch(`/api/suppliers/${s.id}`),
        apiFetch('/api/categories'),
      ]);
      renderDetailView(fresh, freshCats, null);
    });
  }

  document.getElementById('save-edit-btn').addEventListener('click', async () => {
    const btn = document.getElementById('save-edit-btn');
    const msg = document.getElementById('edit-msg');
    btn.disabled = true;
    try {
      const full = {
        name:       document.getElementById('edit-name').value.trim(),
        type:       document.getElementById('edit-type').value,
        trade:      document.getElementById('edit-trade').checked ? 1 : 0,
        website:    document.getElementById('edit-website').value.trim() || null,
        phone:      document.getElementById('edit-phone').value.trim()   || null,
        email:      document.getElementById('edit-email').value.trim()   || null,
        address:    document.getElementById('edit-address').value.trim() || null,
        price_band: document.getElementById('edit-price-band').value     || null,
        notes:      document.getElementById('edit-notes').value.trim()   || null,
      };

      if (isAdmin) {
        await apiFetch(`/api/suppliers/${s.id}`, {
          method: 'PATCH',
          body: JSON.stringify(full),
        });
        if (allCats.length) {
          const ids = [...document.querySelectorAll('input[name="cat"]:checked')].map(el => +el.value);
          await apiFetch(`/api/suppliers/${s.id}/categories`, {
            method: 'PUT',
            body: JSON.stringify({ category_ids: ids }),
          });
        }
        refreshSuppliers();
      } else {
        // Only include fields that differ from the current supplier
        const payload = {};
        for (const [k, v] of Object.entries(full)) {
          if (String(v ?? '') !== String(s[k] ?? '')) payload[k] = v;
        }
        if (allCats.length) {
          const selectedIds = [...document.querySelectorAll('input[name="cat"]:checked')].map(el => +el.value);
          const currentIds  = (s.categories || []).map(c => c.id).sort((a, b) => a - b).join(',');
          const selectedStr = [...selectedIds].sort((a, b) => a - b).join(',');
          if (currentIds !== selectedStr) payload.category_ids = selectedIds;
        }
        if (Object.keys(payload).length === 0) {
          msg.textContent = 'No changes detected.';
          msg.className   = 'form-msg error';
          return;
        }
        await apiFetch('/api/requests', {
          method: 'POST',
          body: JSON.stringify({
            request_type:       'edit',
            target_supplier_id: s.id,
            payload,
          }),
        });
      }

      const [fresh, freshCats, myRequests] = await Promise.all([
        apiFetch(`/api/suppliers/${s.id}`),
        apiFetch('/api/categories'),
        currentUser?.role === 'designer' ? apiFetch('/api/requests') : Promise.resolve([]),
      ]);
      const newPending = (myRequests || []).find(
        r => r.target_supplier_id === s.id && r.status === 'pending'
      ) || null;
      renderDetailView(fresh, freshCats, newPending);
    } catch (err) {
      msg.textContent = err.detail || 'Something went wrong — please try again.';
      msg.className   = 'form-msg error';
    } finally {
      btn.disabled = false;
    }
  });
}

// ── Directions ────────────────────────────────────────────────────────────────
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
    const params = new URLSearchParams({ daddr: destination, dirflg: 'd' });
    if (origin) params.set('saddr', `${origin.lat},${origin.lon}`);
    return `https://maps.apple.com/?${params.toString()}`;
  }

  const params = new URLSearchParams({ api: '1', destination, travelmode: 'driving' });
  if (origin) params.set('origin', `${origin.lat},${origin.lon}`);
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

function openDirections(supplier) {
  const msg = document.getElementById('directions-msg');
  const openTarget = origin => {
    const url = getSupplierDirectionsUrl(supplier, origin);
    if (!url) { if (msg) msg.textContent = 'No address available for directions.'; return; }
    window.open(url, '_blank', 'noopener');
  };
  if (!window.isSecureContext || !navigator.geolocation) { openTarget(null); return; }
  if (msg) msg.textContent = 'Getting your location…';
  navigator.geolocation.getCurrentPosition(
    pos => { if (msg) msg.textContent = ''; openTarget({ lat: pos.coords.latitude, lon: pos.coords.longitude }); },
    ()  => { if (msg) msg.textContent = 'Opening destination only.'; openTarget(null); },
    { maximumAge: 300000, timeout: 4000, enableHighAccuracy: false }
  );
}

function isValidUKPostcode(pc) {
  return /^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-BD-HJLNP-UW-Z]{2}$/i.test(pc.trim());
}

// ── Add Supplier form (admin) ─────────────────────────────────────────────────
function initAddForm() {
  const form = document.getElementById('add-form');
  if (!form) return;
  form.addEventListener('submit', async e => {
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
    if (body.postcode && !isValidUKPostcode(body.postcode)) {
      msg.textContent = 'Invalid UK postcode format.';
      msg.className   = 'form-msg error';
      return;
    }
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

// ── Request add form (designer) ───────────────────────────────────────────────
async function initRequestAddForm() {
  const form = document.getElementById('request-add-form');
  if (!form) return;

  // Populate category checkboxes
  try {
    const cats = await apiFetch('/api/categories');
    const living    = cats.filter(c => c.group_name === 'Living');
    const nonliving = cats.filter(c => c.group_name === 'Non-living');
    const renderGroup = (label, icon, group) => `
      <div class="category-group">
        <h4>${icon} ${label}</h4>
        <div class="cat-checkbox-group">${group.map(c => `<label class="cat-checkbox"><input type="checkbox" name="req-cat" value="${c.id}"> ${esc(c.name)}</label>`).join('')}</div>
      </div>`;
    document.getElementById('request-add-categories').innerHTML =
      `<div style="margin:8px 0 4px;font-size:13px;font-weight:600">Categories</div>` +
      renderGroup('Living', '🌿', living) +
      renderGroup('Non-living', '🪨', nonliving);
  } catch (_) { /* categories optional */ }

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const fd  = new FormData(e.target);
    const msg = document.getElementById('request-add-msg');
    const category_ids = [...form.querySelectorAll('input[name="req-cat"]:checked')].map(el => +el.value);
    const payload = {
      name:         fd.get('name'),
      type:         fd.get('type'),
      areas:        fd.get('area') ? [fd.get('area')] : [],
      website:      fd.get('website')  || null,
      phone:        fd.get('phone')    || null,
      email:        fd.get('email')    || null,
      address:      fd.get('address')  || null,
      postcode:     fd.get('postcode') || null,
      notes:        fd.get('notes')    || null,
      trade:        fd.get('trade') === 'on',
      category_ids: category_ids.length ? category_ids : undefined,
    };
    if (payload.postcode && !isValidUKPostcode(payload.postcode)) {
      msg.textContent = 'Invalid UK postcode format.';
      msg.className   = 'form-msg error';
      return;
    }
    try {
      await apiFetch('/api/requests', {
        method: 'POST',
        body: JSON.stringify({ request_type: 'add', payload }),
      });
      msg.textContent = 'Request submitted — an admin will review it shortly.';
      msg.className   = 'form-msg success';
      e.target.reset();
    } catch (err) {
      msg.textContent = err.detail || 'Something went wrong — please try again.';
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
    } catch { /* ignore */ }
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}
