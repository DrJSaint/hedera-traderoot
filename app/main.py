"""
Hedera TradeRoot — app/main.py
Trade supplier directory for garden designers in South East England.
Built with Streamlit + SQLite + pydeck.

Navigation: tab-based (mobile friendly), no sidebar.
Deep linking: ?supplier=ID loads a single supplier detail view.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import time
import urllib.request
import json
import pandas as pd
import streamlit as st
import pydeck as pdk
import app.db as db

# ── Cached DB wrappers ────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _areas():
    return db.get_all_areas()

@st.cache_data(ttl=300, show_spinner=False)
def _suppliers_with_coords(area, supplier_type):
    return db.get_suppliers_with_coords(area=area, supplier_type=supplier_type)

@st.cache_data(ttl=300, show_spinner=False)
def _suppliers_near(lat, lon, radius, supplier_type):
    return db.get_suppliers_near(lat, lon, radius, supplier_type=supplier_type)

# ── Timing helper ─────────────────────────────────────────────────────────────
# Set TRADEROOT_BENCH=1 in your environment to enable timing output.
_BENCH = os.environ.get("TRADEROOT_BENCH") == "1"

class _Timer:
    def __init__(self, label):
        self.label = label
    def __enter__(self):
        self._start = time.perf_counter()
        return self
    def __exit__(self, *_):
        ms = (time.perf_counter() - self._start) * 1000
        if _BENCH:
            print(f"[bench] {self.label:<45} {ms:7.1f} ms")

def _t(label):
    return _Timer(label)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hedera TradeRoot",
    page_icon="🌿",
    layout="wide"
)

# ── Mobile-friendly CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 12px; font-size: 14px; }
    .block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

st.title("🌿 Hedera TradeRoot")
st.caption("Trade supplier directory for garden designers · South East England")

# ── Deep link detection ───────────────────────────────────────────────────────
params = st.query_params
try:
    deep_link_supplier_id = int(params["supplier"]) if "supplier" in params else None
except (ValueError, KeyError):
    deep_link_supplier_id = None

# ── Reference data ────────────────────────────────────────────────────────────
with _t("db.get_all_areas"):
    areas = _areas()
SUPPLIER_TYPES = ["nursery", "hard_landscaper", "furniture", "lighting", "tools", "other"]
PRICE_BANDS    = ["budget", "mid", "premium"]

# pydeck marker colour by supplier type [R, G, B]
TYPE_COLOURS_RGB = {
    "nursery":         [34,  139, 34],
    "hard_landscaper": [210, 50,  50],
    "furniture":       [65,  105, 225],
    "tools":           [255, 140, 0],
    "lighting":        [148, 0,   211],
    "other":           [120, 120, 120],
}

LEGEND = " &nbsp;&nbsp; ".join([
    "🟢 Nursery", "🔴 Hard Landscaper", "🔵 Furniture",
    "🟠 Tools", "🟣 Lighting", "⚫ Other"
])


# ── Helper functions ──────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def geocode_postcode(postcode: str):
    url = f"https://api.postcodes.io/postcodes/{postcode.replace(' ', '')}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data["status"] == 200:
            return data["result"]["latitude"], data["result"]["longitude"]
    except Exception:
        pass
    return None, None


_MAP_COLS          = ["id", "name", "longitude", "latitude", "type", "phone"]
_MAP_COLS_PROXIMITY = _MAP_COLS + ["distance_miles"]

def _prep_map_df(df: pd.DataFrame, proximity: bool = False) -> pd.DataFrame:
    """Slim to only the columns pydeck needs, then add display columns."""
    cols = _MAP_COLS_PROXIMITY if proximity else _MAP_COLS
    # keep only columns that actually exist (guards against missing optional cols)
    df = df[[c for c in cols if c in df.columns]].copy()
    df["color"]      = df["type"].map(lambda t: TYPE_COLOURS_RGB.get(t, [120, 120, 120]))
    df["type_label"] = df["type"].str.replace("_", " ").str.title()
    df["phone_str"]  = df["phone"].fillna("—").replace("", "—")
    return df


def render_results_list(suppliers: pd.DataFrame, view_key_prefix: str):
    st.subheader(f"Results ({len(suppliers)} suppliers)")

    for _, row in suppliers.iterrows():
        rating_display = f"⭐ {row['avg_rating']:.1f}" if row['review_count'] else "no reviews"

        label = f"**{row['name']}** · {row['type_label']}"
        if "distance_miles" in row.index and pd.notna(row["distance_miles"]):
            label += f" · {row['distance_miles']:.1f} mi"
        label += f" · {rating_display}"

        with st.expander(label):
            st.write(f"📞 {row['phone'] or '—'}")
            st.write(f"🌐 {row['website'] or '—'}")
            if st.button("View full details", key=f"{view_key_prefix}_{row['id']}"):
                st.query_params["supplier"] = str(row["id"])
                st.rerun()


def render_supplier_card(row, expanded=False):
    rating_display = f"⭐ {row['avg_rating']:.1f}" if row['review_count'] else "no reviews"
    with st.expander(
        f"**{row['name']}** · {row['type']} · {rating_display}",
        expanded=expanded
    ):
        st.write(f"📞 {row['phone'] or '—'}")
        st.write(f"📧 {row['email'] or '—'}")
        st.write(f"🌐 {row['website'] or '—'}")
        covered = db.get_supplier_areas(row["id"])
        st.write(f"📍 {', '.join(covered) if covered else '—'}")
        if row['notes']:
            st.write(f"📝 {row['notes']}")

        cats = db.get_supplier_categories(row["id"])
        if cats:
            living    = [c["name"] for c in cats if c["group_name"] == "Living"]
            nonliving = [c["name"] for c in cats if c["group_name"] == "Non-living"]
            st.divider()
            st.subheader("Supplies")
            if living:
                st.write(f"🌿 **Living:** {', '.join(living)}")
            if nonliving:
                st.write(f"🪨 **Non-living:** {', '.join(nonliving)}")

            all_cats          = db.get_all_categories()
            living_options    = [c for c in all_cats if c["group_name"] == "Living"]
            nonliving_options = [c for c in all_cats if c["group_name"] == "Non-living"]
            current_ids       = [c["id"] for c in cats]

            with st.expander("Edit categories"):
                selected_living = st.multiselect(
                    "Living",
                    options=[c["name"] for c in living_options],
                    default=[c["name"] for c in living_options if c["id"] in current_ids],
                    key=f"living_{row['id']}"
                )
                selected_nonliving = st.multiselect(
                    "Non-living",
                    options=[c["name"] for c in nonliving_options],
                    default=[c["name"] for c in nonliving_options if c["id"] in current_ids],
                    key=f"nonliving_{row['id']}"
                )
                if st.button("Save categories", key=f"savecat_{row['id']}"):
                    selected_names = selected_living + selected_nonliving
                    new_ids = [c["id"] for c in all_cats if c["name"] in selected_names]
                    db.set_supplier_categories(row["id"], new_ids)
                    st.success("Categories updated!")
                    st.rerun()

        st.divider()
        st.subheader("Reviews")
        reviews = db.get_reviews_for_supplier(row["id"])
        if reviews.empty:
            st.write("No reviews yet.")
        else:
            for _, rev in reviews.iterrows():
                stars       = "⭐" * int(rev["rating"])
                company_str = f" · {rev['designer_company']}" if rev.get('designer_company') else ""
                st.write(f"{stars} — *{rev['review_text']}*")
                st.caption(f"{rev['designer']}{company_str} · {rev['job_area'] or ''} · {rev['created_at'][:10]}")

        designers = db.get_all_designers()
        if designers:
            with st.expander("✍️ Leave a review"):
                designer_options = {
                    f"{d['name']}{' · ' + d['company'] if d.get('company') else ''}": d["id"]
                    for d in designers
                }
                selected_designer = st.selectbox(
                    "Your name",
                    list(designer_options.keys()),
                    key=f"rev_designer_{row['id']}"
                )
                rating   = st.slider("Rating", 1, 5, 3, key=f"rev_rating_{row['id']}")
                job_area = st.text_input("County", key=f"rev_area_{row['id']}")
                review   = st.text_area("Your review", key=f"rev_text_{row['id']}")

                if st.button("Submit review", key=f"rev_submit_{row['id']}"):
                    if not review:
                        st.warning("Please write a review before submitting.")
                    else:
                        db.add_review(
                            row["id"],
                            designer_options[selected_designer],
                            rating, review, job_area
                        )
                        st.success("Review submitted — thank you!")
                        st.rerun()
        else:
            st.caption("Register as a designer to leave a review.")

        if st.button("Delete supplier", key=f"del_{row['id']}"):
            st.session_state[f"confirm_delete_{row['id']}"] = True

        if st.session_state.get(f"confirm_delete_{row['id']}"):
            st.warning("Are you sure you want to delete this supplier?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes, delete", key=f"confirm_{row['id']}"):
                    db.delete_supplier(row["id"])
                    st.success("Supplier deleted.")
                    st.query_params.clear()
                    st.rerun()
            with col2:
                if st.button("Cancel", key=f"cancel_{row['id']}"):
                    st.session_state[f"confirm_delete_{row['id']}"] = False
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Deep link view
# ══════════════════════════════════════════════════════════════════════════════
if deep_link_supplier_id:
    supplier = db.get_supplier_by_id(deep_link_supplier_id)
    if supplier:
        st.header("Supplier Details")
        if st.button("← Back"):
            st.query_params.clear()
            st.rerun()
        render_supplier_card(supplier, expanded=True)
    else:
        st.error("Supplier not found.")
        st.query_params.clear()

else:
    tab_browse, tab_map, tab_add, tab_register = st.tabs([
        "🔍 Browse", "🗺️ Map", "➕ Add Supplier", "👤 Register"
    ])

    # ── Browse tab ────────────────────────────────────────────────────────────
    with tab_browse:
        col1, col2 = st.columns(2)
        with col1:
            filter_area = st.selectbox("Filter by area", ["All"] + areas, key="browse_area")
        with col2:
            filter_type = st.selectbox("Filter by type", ["All"] + SUPPLIER_TYPES, key="browse_type")

        area  = None if filter_area == "All" else filter_area
        stype = None if filter_type == "All" else filter_type

        suppliers = db.get_suppliers(area=area, supplier_type=stype)

        if suppliers.empty:
            st.info("No suppliers found. Try adjusting your filters.")
        else:
            st.write(f"**{len(suppliers)} supplier(s) found**")
            for _, row in suppliers.iterrows():
                render_supplier_card(row)

    # ── Map tab ───────────────────────────────────────────────────────────────
    with tab_map:
        st.markdown(LEGEND)

        col1, col2 = st.columns(2)
        with col1:
            filter_area = st.selectbox("Filter by area", ["All"] + areas, key="map_area")
        with col2:
            filter_type = st.selectbox("Filter by type", ["All"] + SUPPLIER_TYPES, key="map_type")

        area  = None if filter_area == "All" else filter_area
        stype = None if filter_type == "All" else filter_type

        st.divider()
        st.subheader("📍 Find near a location")

        # ── Postcode search ───────────────────────────────────────────────────
        if "pc" not in st.session_state:
            st.session_state["pc"] = ""
        if "pc_version" not in st.session_state:
            st.session_state["pc_version"] = 0

        col1, col2 = st.columns(2)
        with col1:
            new_pc = st.text_input(
                "Enter a postcode",
                placeholder="e.g. RH10 9RX",
                value=st.session_state["pc"],
                key=f"postcode_field_{st.session_state['pc_version']}"
            )
            if new_pc != st.session_state["pc"]:
                st.session_state["pc"] = new_pc
        with col2:
            radius = st.slider("Radius (miles)", 5, 100, 25)

        postcode = st.session_state["pc"]
        lat, lon, source = None, None, None

        if postcode:
            _geo_cache = st.session_state.setdefault("_geo_cache", {})
            if postcode not in _geo_cache:
                with _t(f"geocode_postcode({postcode})"):
                    _geo_cache[postcode] = geocode_postcode(postcode)
            lat, lon = _geo_cache[postcode]
            source = postcode.upper()
            if lat is None:
                st.error("Postcode not found — please check and try again.")

        if postcode:
            if st.button("✕ Clear location", key="clear_location"):
                st.session_state["pc"] = ""
                st.session_state["pc_version"] += 1
                st.rerun()

        st.divider()

        # ── Proximity mode ────────────────────────────────────────────────────
        if lat is not None and lon is not None:
            with _t("db.get_suppliers_near (bbox SQL)"):
                candidates = _suppliers_near(lat, lon, radius, stype)

            with _t(f"haversine apply ({len(candidates)} candidates)"):
                candidates["distance_miles"] = candidates.apply(
                    lambda r: haversine(lat, lon, r["latitude"], r["longitude"]), axis=1
                )
            suppliers = candidates[
                candidates["distance_miles"] <= radius
            ].sort_values("distance_miles").reset_index(drop=True)

            suppliers = _prep_map_df(suppliers, proximity=True)

            st.success(f"**{len(suppliers)} supplier(s)** within {radius} miles of **{source}**")

            home_df = pd.DataFrame([{"lon": lon, "lat": lat}])

            with _t("pydeck render (proximity)"):
                st.pydeck_chart(pdk.Deck(
                    layers=[
                        # Radius circle
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=home_df,
                            get_position=["lon", "lat"],
                            get_color=[100, 100, 100, 20],
                            get_radius=radius * 1609.34,
                            stroked=True,
                            line_width_min_pixels=2,
                            get_line_color=[80, 80, 80, 160],
                        ),
                        # Suppliers
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=suppliers,
                            get_position=["longitude", "latitude"],
                            get_color="color",
                            get_radius=2000,
                            radius_min_pixels=5,
                            radius_max_pixels=14,
                            pickable=True,
                            auto_highlight=True,
                        ),
                        # Home pin
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=home_df,
                            get_position=["lon", "lat"],
                            get_color=[0, 0, 0, 220],
                            get_radius=1500,
                            radius_min_pixels=8,
                            radius_max_pixels=16,
                        ),
                    ],
                    initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=9),
                    tooltip={
                        "html": "<b>{name}</b><br><i>{type_label}</i><br>📍 {distance_miles:.1f} mi<br>📞 {phone_str}",
                        "style": {"backgroundColor": "white", "color": "#333", "fontSize": "12px", "padding": "8px"},
                    },
                    map_provider="carto",
                    map_style="light",
                ))

            render_results_list(suppliers, "prox_view")

        # ── National map mode ─────────────────────────────────────────────────
        else:
            with _t("db.get_suppliers_with_coords (national)"):
                suppliers = _suppliers_with_coords(area, stype)

            if suppliers.empty:
                st.info("No suppliers with location data found.")
            else:
                suppliers = _prep_map_df(suppliers)
                st.write(f"**{len(suppliers)} supplier(s) on map**")

                with _t("pydeck render (national)"):
                    st.pydeck_chart(pdk.Deck(
                        layers=[
                            pdk.Layer(
                                "ScatterplotLayer",
                                data=suppliers,
                                get_position=["longitude", "latitude"],
                                get_color="color",
                                get_radius=3000,
                                radius_min_pixels=4,
                                radius_max_pixels=14,
                                pickable=True,
                                auto_highlight=True,
                            )
                        ],
                        initial_view_state=pdk.ViewState(latitude=52.5, longitude=-1.5, zoom=6),
                        tooltip={
                            "html": "<b>{name}</b><br><i>{type_label}</i><br>📞 {phone_str}",
                            "style": {"backgroundColor": "white", "color": "#333", "fontSize": "12px", "padding": "8px"},
                        },
                        map_provider="carto",
                    map_style="light",
                    ))

                render_results_list(suppliers, "nat_view")

    # ── Add Supplier tab ──────────────────────────────────────────────────────
    with tab_add:
        st.subheader("Add a Supplier")

        name       = st.text_input("Business name *")
        stype      = st.selectbox("Type *", SUPPLIER_TYPES)
        price_band = st.selectbox("Price band", PRICE_BANDS)
        covered    = st.multiselect("Areas covered", areas)
        website    = st.text_input("Website")
        phone      = st.text_input("Phone")
        email      = st.text_input("Email")
        notes      = st.text_area("Notes")

        if st.button("Add supplier"):
            if not name:
                st.warning("Business name is required.")
            else:
                db.add_supplier(name, stype, website, phone, email, price_band, notes, covered)
                st.success(f"**{name}** added successfully!")

    # ── Register tab ──────────────────────────────────────────────────────────
    with tab_register:
        st.subheader("Register as a Designer")

        name    = st.text_input("Your name *")
        email   = st.text_input("Your email *")
        company = st.text_input("Company name (optional)")

        if st.button("Register"):
            if not name or not email:
                st.warning("Name and email are required.")
            else:
                try:
                    db.add_designer(name, email, company)
                    st.success(f"Welcome, {name}! You can now leave reviews.")
                except Exception:
                    st.error("That email address is already registered.")
