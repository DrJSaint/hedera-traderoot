"""
Hedera TradeRoot
Trade supplier directory for garden designers in South East England. Awsome Stuff
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import app.db as db

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
    ["Browse Suppliers", "Add Supplier", "Add Review", "Register as Designer"]
)

areas = db.get_all_areas()
SUPPLIER_TYPES = ["nursery", "hard_landscaper", "furniture", "lighting", "tools", "other"]
PRICE_BANDS = ["budget", "mid", "premium"]

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