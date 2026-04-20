# 🌿 Hedera TradeRoot

> *Trade supplier directory for garden designers in South East England.*

Built by [Hedera Garden Design](https://hederagardendesign.co.uk) to help fellow designers find the best nurseries, hard landscapers, furniture suppliers, and contractors for jobs across the region.

## Live App

[hedera-traderoot.streamlit.app](https://hedera-traderoot.streamlit.app)

## What it does

- **Browse suppliers** — filter by area and type, view ratings, categories, and reviews
- **Map view** — interactive map with coloured markers by supplier type, click to filter results
- **Find near a location** — enter a postcode or use device geolocation to find suppliers within a radius
- **Leave reviews** — designers can rate and review suppliers directly on the supplier card
- **Add suppliers** — any user can add a new supplier to the directory
- **Register as a designer** — register with name, email, and company to leave reviews

## Stack

- **Python 3.11+**
- **Streamlit** — UI and mobile-friendly tab navigation
- **SQLite** — database (via Python standard library)
- **Folium + streamlit-folium** — interactive maps
- **streamlit-geolocation** — device location detection
- **Postcodes.io** — free UK postcode geocoding (no API key needed)
- **GitHub Codespaces** — cloud development environment

## Running locally

```bash
streamlit run app/main.py
```

## Project structure

```
hedera-traderoot/
├── .devcontainer/
│   └── devcontainer.json       # Codespaces configuration
├── app/
│   ├── main.py                 # Streamlit app
│   └── db.py                   # Database access layer
├── database/
│   ├── schema.sql              # Database schema
│   ├── init_db.py              # Initialise database
│   └── traderoot.db            # SQLite database
├── data/
│   └── hta_members.csv         # Scraped HTA member data
├── scripts/
│   ├── scrape_hta.py           # Scrape HTA member directory
│   ├── import_hta.py           # Bulk import scraped data
│   ├── migrate_add_categories.py  # Migration: add categories tables
│   ├── migrate_add_company.py     # Migration: add company to designers
│   ├── seed_fake_data.py       # Seed fake designers, reviews, categories
│   ├── randomise_types.py      # Randomly assign supplier types (demo)
│   └── update_types.py         # Map HTA tags to supplier types
└── requirements.txt
```

## Database schema

| Table | Purpose |
|---|---|
| `suppliers` | The businesses being reviewed |
| `areas` | Counties / regions |
| `supplier_areas` | Many-to-many: supplier ↔ area |
| `categories` | Supply categories (Living / Non-living) |
| `supplier_categories` | Many-to-many: supplier ↔ category |
| `designers` | Garden designers who leave reviews |
| `reviews` | Ratings and text reviews |

### Supply categories

**Living:** Trees, Shrubs, Perennials, Grasses, Alpine, Hedging, Climbers

**Non-living:** Paving, Gravel, Decking, Fencing, Trellis, Pergola/Arbour

## Roadmap

- [ ] Authentication (streamlit-authenticator)
- [ ] Edit supplier details
- [ ] Hedera branding and theming
- [ ] Move to PostgreSQL + Supabase for production
- [ ] Scrape additional supplier types (Landscaper, Grower, Retailer)
- [ ] Real West Sussex supplier data from Eleanor
- [ ] Proximity search improvements
