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

st.set_page_config(
    page_title="Hedera TradeRoot",
    page_icon="🌿",
    layout="wide"
)

st.title("🌿 Hedera TradeRoot")
st.caption("Trade supplier directory for garden designers · South East England")

# ── Sidebar navigation ────────────────────────────────────────────────────────
page = st.sidebar.radio(
    "Navigate",
    ["Browse Suppliers", "Map View", "Find Near Postcode",
     "Add Supplier", "Add Review", "Register as Designer"]
)

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

# ── Haversine distance (miles) ────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# ── Geocode postcode via Postcodes.io ─────────────────────────────────────────
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

# ── Browse Suppliers ──────────────────────────────────────────────────────────
if page == "Browse Suppliers":
    st.header("Browse Suppliers")

    col1, col2 = st.columns(2)
    with col1:
        filter_area = st.selectbox("Filter by area", ["All"] + areas)
    with col2:
        filter_type = st.selectbox("Filter by type", ["All"] + SUPPLIER_TYPES)

    area = None if filter_area == "All" else filter_area
    stype = None if filter_type == "All" else filter_type

    suppliers = db.get_suppliers(area=area, supplier_type=stype)

    if suppliers.empty:
        st.info("No suppliers found. Try adjusting your filters or add one.")
    else:
        st.write(f"**{len(suppliers)} supplier(s) found**")
        for _, row in suppliers.iterrows():
            with st.expander(f"**{row['name']}** · {row['type']} · {row['price_band'] or 'price n/a'}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📞 {row['phone'] or '—'}")
                    st.write(f"📧 {row['email'] or '—'}")
                    st.write(f"🌐 {row['website'] or '—'}")
                with col2:
                    covered = db.get_supplier_areas(row["id"])
                    st.write(f"📍 Areas: {', '.join(covered) if covered else '—'}")
                    st.write(f"📝 {row['notes'] or '—'}")

                st.divider()
                st.subheader("Reviews")
                reviews = db.get_reviews_for_supplier(row["id"])
                if reviews.empty:
                    st.write("No reviews yet.")
                else:
                    for _, rev in reviews.iterrows():
                        stars = "⭐" * int(rev["rating"])
                        st.write(f"{stars} — *{rev['review_text']}*")
                        st.caption(f"{rev['designer']} · {rev['job_area'] or ''} · {rev['created_at'][:10]}")

                if st.button("Delete supplier", key=f"del_{row['id']}"):
                    st.session_state[f"confirm_delete_{row['id']}"] = True

                if st.session_state.get(f"confirm_delete_{row['id']}"):
                    st.warning("Are you sure you want to delete this supplier?")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Yes, delete", key=f"confirm_{row['id']}"):
                            db.delete_supplier(row["id"])
                            st.success("Supplier deleted.")
                            st.rerun()
                    with col2:
                        if st.button("Cancel", key=f"cancel_{row['id']}"):
                            st.session_state[f"confirm_delete_{row['id']}"] = False
                            st.rerun()

# ── Map View ──────────────────────────────────────────────────────────────────
elif page == "Map View":
    st.header("Supplier Map")

    col1, col2 = st.columns(2)
    with col1:
        filter_area = st.selectbox("Filter by area", ["All"] + areas)
    with col2:
        filter_type = st.selectbox("Filter by type", ["All"] + SUPPLIER_TYPES)

    area = None if filter_area == "All" else filter_area
    stype = None if filter_type == "All" else filter_type

    suppliers = db.get_suppliers_with_coords(area=area, supplier_type=stype)

    legend_items = {
        "green":  "🟢 Nursery",
        "red":    "🔴 Hard Landscaper",
        "blue":   "🔵 Furniture",
        "orange": "🟠 Tools",
        "purple": "🟣 Lighting",
        "gray":   "⚫ Other",
    }
    st.markdown(" &nbsp;&nbsp; ".join(legend_items.values()))

    if suppliers.empty:
        st.info("No suppliers with location data found.")
    else:
        st.write(f"**{len(suppliers)} supplier(s) on map**")
        m = folium.Map(location=[52.5, -1.5], zoom_start=6)

        for _, row in suppliers.iterrows():
            colour = TYPE_COLOURS.get(row["type"], "gray")
            popup_html = f"""
                <b>{row['name']}</b><br>
                <i>{row['type'].replace('_', ' ').title()}</i><br>
                📞 {row['phone'] or '—'}<br>
                🌐 <a href="{row['website'] or '#'}" target="_blank">Website</a>
            """
            folium.Marker(
                location=[row["latitude"], row["longitude"]],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=row["name"],
                icon=folium.Icon(color=colour, icon="leaf", prefix="fa")
            ).add_to(m)

        st_folium(m, use_container_width=True, height=600)

# ── Find Near Postcode ────────────────────────────────────────────────────────
elif page == "Find Near Postcode":
    st.header("Find Suppliers Near a Postcode")

    col1, col2, col3 = st.columns(3)
    with col1:
        postcode = st.text_input("Postcode", placeholder="e.g. RH10 9RX")
    with col2:
        radius = st.slider("Radius (miles)", 5, 100, 25)
    with col3:
        filter_type = st.selectbox("Filter by type", ["All"] + SUPPLIER_TYPES)

    if postcode:
        lat, lon = geocode_postcode(postcode)

        if lat is None:
            st.error("Postcode not found — please check and try again.")
        else:
            st.success(f"Searching within {radius} miles of **{postcode.upper()}**")

            all_suppliers = db.get_all_suppliers_with_coords()

            # Filter by type
            if filter_type != "All":
                all_suppliers = all_suppliers[all_suppliers["type"] == filter_type]

            # Calculate distances
            all_suppliers["distance_miles"] = all_suppliers.apply(
                lambda r: haversine(lat, lon, r["latitude"], r["longitude"]), axis=1
            )

            # Filter by radius
            nearby = all_suppliers[
                all_suppliers["distance_miles"] <= radius
            ].sort_values("distance_miles")

            if nearby.empty:
                st.info(f"No suppliers found within {radius} miles. Try increasing the radius.")
            else:
                st.write(f"**{len(nearby)} supplier(s) found**")

                # Map
                m = folium.Map(location=[lat, lon], zoom_start=9)

                # Postcode marker
                folium.Marker(
                    location=[lat, lon],
                    tooltip=postcode.upper(),
                    icon=folium.Icon(color="black", icon="home", prefix="fa")
                ).add_to(m)

                # Radius circle
                folium.Circle(
                    location=[lat, lon],
                    radius=radius * 1609.34,  # convert miles to metres
                    color="gray",
                    fill=True,
                    fill_opacity=0.05
                ).add_to(m)

                # Supplier markers
                for _, row in nearby.iterrows():
                    colour = TYPE_COLOURS.get(row["type"], "gray")
                    popup_html = f"""
                        <b>{row['name']}</b><br>
                        <i>{row['type'].replace('_', ' ').title()}</i><br>
                        📍 {row['distance_miles']:.1f} miles away<br>
                        📞 {row['phone'] or '—'}<br>
                        🌐 <a href="{row['website'] or '#'}" target="_blank">Website</a>
                    """
                    folium.Marker(
                        location=[row["latitude"], row["longitude"]],
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=f"{row['name']} ({row['distance_miles']:.1f} mi)",
                        icon=folium.Icon(color=colour, icon="leaf", prefix="fa")
                    ).add_to(m)

                st_folium(m, use_container_width=True, height=500)

                # Results table
                st.subheader("Results")
                for _, row in nearby.iterrows():
                    with st.expander(
                        f"**{row['name']}** · {row['type']} · "
                        f"{row['distance_miles']:.1f} miles"
                    ):
                        st.write(f"📞 {row['phone'] or '—'}")
                        st.write(f"🌐 {row['website'] or '—'}")
                        st.write(f"📝 {row['notes'] or '—'}")

# ── Add Supplier ──────────────────────────────────────────────────────────────
elif page == "Add Supplier":
    st.header("Add a Supplier")

    name        = st.text_input("Business name *")
    stype       = st.selectbox("Type *", SUPPLIER_TYPES)
    price_band  = st.selectbox("Price band", PRICE_BANDS)
    covered     = st.multiselect("Areas covered", areas)
    website     = st.text_input("Website")
    phone       = st.text_input("Phone")
    email       = st.text_input("Email")
    notes       = st.text_area("Notes")

    if st.button("Add supplier"):
        if not name:
            st.warning("Business name is required.")
        else:
            db.add_supplier(name, stype, website, phone, email, price_band, notes, covered)
            st.success(f"**{name}** added successfully!")

# ── Add Review ────────────────────────────────────────────────────────────────
elif page == "Add Review":
    st.header("Leave a Review")

    suppliers = db.get_suppliers()
    designers = db.get_all_designers()

    if suppliers.empty:
        st.info("No suppliers in the database yet.")
    elif not designers:
        st.info("No designers registered yet. Please register first.")
    else:
        supplier_options = {row["name"]: row["id"] for _, row in suppliers.iterrows()}
        designer_options = {d["name"]: d["id"] for d in designers}

        selected_supplier = st.selectbox("Supplier", list(supplier_options.keys()))
        selected_designer = st.selectbox("Your name", list(designer_options.keys()))
        rating    = st.slider("Rating", 1, 5, 3)
        job_area  = st.text_input("County where job was based")
        review    = st.text_area("Your review")

        if st.button("Submit review"):
            db.add_review(
                supplier_options[selected_supplier],
                designer_options[selected_designer],
                rating, review, job_area
            )
            st.success("Review submitted — thank you!")

# ── Register Designer ─────────────────────────────────────────────────────────
elif page == "Register as Designer":
    st.header("Register as a Designer")

    name  = st.text_input("Your name *")
    email = st.text_input("Your email *")

    if st.button("Register"):
        if not name or not email:
            st.warning("Name and email are required.")
        else:
            try:
                db.add_designer(name, email)
                st.success(f"Welcome, {name}! You can now leave reviews.")
            except Exception:
                st.error("That email address is already registered.")
