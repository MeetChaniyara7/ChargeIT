# API Data Ingestion Scripts

This directory contains data ingestion scripts to sync charging station data from external APIs directly into your local PostgreSQL database (`ev_charging`).

## How to Run Ingestion

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Run the ingestion script:
   ```bash
   python scripts/ingest_stations.py
   ```

3. Open **DBeaver** or query FastAPI (`http://localhost:8000/api/stations`) to see the newly synced charging stations!
