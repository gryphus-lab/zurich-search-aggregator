#!/bin/bash
cd /app

echo "=== Zurich Apartment Scraper started at $(date) ==="

# Run with your preferred filters (adjust as needed)
mise run scrape \
  --min 2000 \
  --max 2500 \
  --neigh Oerlikon \
  --json results/latest.json \
  --flexible

echo "=== Scrape finished. Listings saved to results/latest.json ==="
ls -l results/latest.json