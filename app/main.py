"""
Hedera TradeRoot
Trade supplier directory for garden designers in South East England.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import urllib.request
import json
import streamlit as st
import app.db as db
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(
    page_title="Hedera TradeRoot",
    page_icon="🌿",
    layout="wide"
)

# ── Mobile-friendly CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Hide sidebar entirely */
    [data-testid="stSidebar"] { display: none; }
    /* Tighten up tab bar */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 12px; font-size: 14px; }
    /* Reduce top padding on mobile */
    .block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

st.title("🌿 Hedera TradeRoot")
st.caption("Trade supplier directory for garden designers · South East England")

# ── Query param deep linking ──────────────────────────────────────────────────
params = st.query_params
deep_link_supplier_id = int(params["supplier"]) if "supplier" in params else None

areas = db.get_all_areas()
SUPPLIER_TYPES = ["nursery", "hard_landscaper", "furniture", "lighting", "tools", "other"]
PRICE_BANDS = ["budget", "mid", "premium"]

TYPE_COLOURS = {
    "nursery":         "green",
    "hard_landscaper": "red",
    "furniture":       "blue",
    "tools":           "orange",
    "lighting":        "purple",
    "other":           "gray",
}

LEGEND = " &nbsp;&nbsp; ".join([
    "🟢 Nursery", "🔴 Hard Landscaper", "🔵 Furniture",
    "🟠 Tools", "🟣 Lighting", "⚫ Other"
])

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def geocode_postcode(postcode):
    url = f"https://api.postcodes.io/postcodes/{postcode.replace(' ', '')}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data["status"] == 200:
            return data["result"]["latitude"], data["result"]["longitude"]
    except Exception:
        pass
    return None, None

def supplier_popup(row, include_distance=False):
    rating_str = f"⭐ {row['avg_rating']:.1f} ({int(row['review_count'])} reviews)" \
        if row['review_count'] else "No reviews yet"
    dist = f"<br>📍 {row['distance_miles']:.1f} miles away" \
        if include_distance and 'distance_miles' in row.index else ""
    return f"""
        <b>{row['name']}</b><br>
        <i>{row['type'].replace('_', ' ').title()}</i><br>
        {rating_str}<br>
        📞 {row['phone'] or '—'}<br>
        🌐 <a href="{row['website'] or '#'}" target="_blank">Website</a>{dist}
    """

def supplier_tooltip(row):
    if row['review_count']:
        return f"{row['name']} ⭐{row['avg_rating']:.1f}"
    return row['name']

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

            all_cats = db.get_all_categories()
            living_options    = [c for c in all_cats if c["group_name"] == "Living"]
            nonliving_options = [c for c in all_cats if c["group_name"] == "Non-living"]
            current_ids = [c["id"] for c in cats]

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
                stars = "⭐" * int(rev["rating"])
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

# ── Deep link: show single supplier from any tab ──────────────────────────────
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
    # ── Tab navigation ────────────────────────────────────────────────────────
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

        area = None if filter_area == "All" else filter_area
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

        area = None if filter_area == "All" else filter_area
        stype = None if filter_type == "All" else filter_type

        st.divider()
        st.subheader("📍 Find near a location")

        location = streamlit_geolocation()

        col1, col2, col3 = st.columns(3)
        with col1:
            postcode = st.text_input("Or enter a postcode", placeholder="e.g. RH10 9RX")
        with col2:
            radius = st.slider("Radius (miles)", 5, 100, 25)
        with col3:
            use_location = st.checkbox("Search by location", value=False)

        lat, lon, source = None, None, None

        if use_location:
            if location and location.get("latitude"):
                lat = location["latitude"]
                lon = location["longitude"]
                source = "your device location"
            elif postcode:
                lat, lon = geocode_postcode(postcode)
                source = postcode.upper()
                if lat is None:
                    st.error("Postcode not found — please check and try again.")

        st.divider()

        if lat and lon:
            all_suppliers = db.get_all_suppliers_with_coords()
            if stype:
                all_suppliers = all_suppliers[all_suppliers["type"] == stype]

            all_suppliers["distance_miles"] = all_suppliers.apply(
                lambda r: haversine(lat, lon, r["latitude"], r["longitude"]), axis=1
            )
            suppliers = all_suppliers[
                all_suppliers["distance_miles"] <= radius
            ].sort_values("distance_miles")

            st.success(f"**{len(suppliers)} supplier(s)** within {radius} miles of **{source}**")

            m = folium.Map(location=[lat, lon], zoom_start=9)
            folium.Marker(
                location=[lat, lon],
                tooltip=source,
                icon=folium.Icon(color="black", icon="home", prefix="fa")
            ).add_to(m)
            folium.Circle(
                location=[lat, lon],
                radius=radius * 1609.34,
                color="gray", fill=True, fill_opacity=0.05
            ).add_to(m)

            for _, row in suppliers.iterrows():
                colour = TYPE_COLOURS.get(row["type"], "gray")
                folium.Marker(
                    location=[row["latitude"], row["longitude"]],
                    popup=folium.Popup(supplier_popup(row, include_distance=True), max_width=250),
                    tooltip=f"{supplier_tooltip(row)} · {row['distance_miles']:.1f} mi",
                    icon=folium.Icon(color=colour, icon="leaf", prefix="fa")
                ).add_to(m)

            st_folium(m, use_container_width=True, height=400)

            st.subheader("Results")
            for _, row in suppliers.iterrows():
                rating_display = f"⭐ {row['avg_rating']:.1f}" if row['review_count'] else "no reviews"
                with st.expander(
                    f"**{row['name']}** · {row['type']} · "
                    f"{row['distance_miles']:.1f} mi · {rating_display}"
                ):
                    st.write(f"📞 {row['phone'] or '—'}")
                    st.write(f"🌐 {row['website'] or '—'}")
                    if st.button("View full details", key=f"prox_view_{row['id']}"):
                        st.query_params["supplier"] = str(row["id"])
                        st.rerun()

        else:
            suppliers = db.get_suppliers_with_coords(area=area, supplier_type=stype)

            if suppliers.empty:
                st.info("No suppliers with location data found.")
            else:
                st.write(f"**{len(suppliers)} supplier(s) on map**")
                m = folium.Map(location=[52.5, -1.5], zoom_start=6)

                for _, row in suppliers.iterrows():
                    colour = TYPE_COLOURS.get(row["type"], "gray")
                    folium.Marker(
                        location=[row["latitude"], row["longitude"]],
                        popup=folium.Popup(supplier_popup(row), max_width=250),
                        tooltip=supplier_tooltip(row),
                        icon=folium.Icon(color=colour, icon="leaf", prefix="fa")
                    ).add_to(m)

                map_data = st_folium(m, use_container_width=True, height=500)

                # Track clicked marker
                clicked = map_data.get("last_object_clicked") if map_data else None
                if clicked:
                    click_lat = clicked.get("lat")
                    click_lng = clicked.get("lng")
                    if click_lat and click_lng:
                        for _, row in suppliers.iterrows():
                            if (abs(row["latitude"] - click_lat) < 0.0001 and
                                    abs(row["longitude"] - click_lng) < 0.0001):
                                st.session_state["map_clicked"] = row["id"]
                                break

                clicked_supplier = st.session_state.get("map_clicked")

                if clicked_supplier and clicked_supplier in suppliers["id"].values:
                    st.subheader("Selected Supplier")
                    if st.button("← Show all", key="reset_map"):
                        st.session_state.pop("map_clicked", None)
                        st.rerun()
                    display_suppliers = suppliers[suppliers["id"] == clicked_supplier]
                else:
                    st.session_state["map_clicked"] = None
                    st.subheader(f"Results ({len(suppliers)} suppliers)")
                    st.caption("Click a marker on the map to filter.")
                    display_suppliers = suppliers

                for _, row in display_suppliers.iterrows():
                    rating_display = f"⭐ {row['avg_rating']:.1f}" if row['review_count'] else "no reviews"
                    with st.expander(
                        f"**{row['name']}** · {row['type']} · {rating_display}",
                        expanded=clicked_supplier == row["id"]
                    ):
                        st.write(f"📞 {row['phone'] or '—'}")
                        st.write(f"🌐 {row['website'] or '—'}")
                        if st.button("View full details", key=f"nat_view_{row['id']}"):
                            st.query_params["supplier"] = str(row["id"])
                            st.rerun()

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
