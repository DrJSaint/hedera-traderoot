# 🌿 Hedera TradeRoot

> *Trade supplier directory for garden designers in South East England.*

Built by [Hedera Garden Design](https://hederagardendesign.co.uk) to help 
fellow designers find the best nurseries, hard landscapers, furniture 
suppliers, and contractors for jobs across the region.

## Live App

[hedera-traderoot.streamlit.app](https://hedera-traderoot.streamlit.app)

## Stack

- **Python 3.11+**
- **Streamlit** — UI
- **SQLite** — database
- **Folium** — interactive maps
- **Postcodes.io** — free UK postcode geocoding
- **GitHub Codespaces** — development environment

## Running locally

```bash
streamlit run app/main.py
```

## Database Schema

| Table | Purpose |
|---|---|
| `suppliers` | The businesses being reviewed |
| `areas` | Counties / regions |
| `supplier_areas` | Many-to-many: supplier ↔ area |
| `categories` | Supply categories (Living / Non-living) |
| `supplier_categories` | Many-to-many: supplier ↔ category |
| `designers` | Garden designers who leave reviews |
| `reviews` | Ratings and text reviews |

## Roadmap

- [ ] Authentication
- [ ] Edit supplier details
- [ ] Streamlit theming / mobile UI
- [ ] PostgreSQL for production
