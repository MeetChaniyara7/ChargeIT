import os
import sys
import requests
from dotenv import load_dotenv

# Ensure parent backend directory is in path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Station, Charger

load_dotenv()

# External API endpoint (e.g. OpenChargeMap API or custom partner API)
EXTERNAL_API_URL = os.getenv(
    "EXTERNAL_API_URL",
    "https://api.openchargemap.io/v3/poi/?output=json&maxresults=10&compact=true"
)

def sync_external_stations():
    """
    Ingestion script to fetch EV charging stations from an external API 
    and store/update them in local PostgreSQL database.
    """
    print(f"📡 Fetching external charging station data from {EXTERNAL_API_URL}...")
    
    db = SessionLocal()
    
    try:
        response = requests.get(EXTERNAL_API_URL, timeout=10)
        
        # If external API is unreachable or requires key, use seed dataset
        if response.status_code != 200 or not isinstance(response.json(), list):
            print("⚠️ External API response unavailable or requires API key. Using seed dataset.")
            raw_stations = [
                {
                    "title": "VoltPulse Supercharge Hub - Downtown",
                    "address": "101 Electric Ave, Metro City",
                    "lat": 37.7749,
                    "lng": -122.4194,
                    "chargers": [
                        {"type": "CCS2", "power": 150.0, "price": 18.5},
                        {"type": "Type 2", "power": 22.0, "price": 12.0}
                    ]
                },
                {
                    "title": "EcoCharge Plaza - Tech Park",
                    "address": "450 Innovation Blvd, Silicon Valley",
                    "lat": 37.3861,
                    "lng": -122.0839,
                    "chargers": [
                        {"type": "CCS2", "power": 120.0, "price": 16.0},
                        {"type": "CHAdeMO", "power": 50.0, "price": 14.0}
                    ]
                },
                {
                    "title": "GreenDrive Station - Airport Express",
                    "address": "789 Airport Loop, Terminal 2",
                    "lat": 37.6213,
                    "lng": -122.3790,
                    "chargers": [
                        {"type": "CCS2", "power": 250.0, "price": 22.0}
                    ]
                }
            ]
        else:
            raw_stations = []
            for item in response.json():
                addr_info = item.get("AddressInfo", {})
                raw_stations.append({
                    "title": addr_info.get("Title", "EV Charging Location"),
                    "address": addr_info.get("AddressLine1", "Unknown Address"),
                    "lat": addr_info.get("Latitude", 0.0),
                    "lng": addr_info.get("Longitude", 0.0),
                    "chargers": [{"type": "CCS2", "power": 50.0, "price": 15.0}]
                })

        inserted_count = 0
        for item in raw_stations:
            # Check if station already exists by name to prevent duplication
            existing = db.query(Station).filter(Station.name == item["title"]).first()
            if not existing:
                new_station = Station(
                    name=item["title"],
                    address=item["address"],
                    latitude=item["lat"],
                    longitude=item["lng"]
                )
                db.add(new_station)
                db.flush()  # Populates new_station.station_id

                # Add associated chargers
                for ch in item.get("chargers", []):
                    charger = Charger(
                        station_id=new_station.station_id,
                        type=ch["type"],
                        power_kw=ch["power"],
                        price_per_kwh=ch["price"],
                        status="AVAILABLE"
                    )
                    db.add(charger)

                inserted_count += 1

        db.commit()
        print(f"✅ Ingestion complete! Successfully inserted {inserted_count} new charging stations into local PostgreSQL.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error during ingestion: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    sync_external_stations()
