import os
import math
from typing import List
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from dotenv import load_dotenv

from database import get_db, engine, Base
import models
import schemas
from auth.jwt import get_current_user
from routes.auth import router as auth_router, api_router

load_dotenv()

# Automatically create all 7 missing tables in local PostgreSQL if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="VoltPulse EV Charging Platform API",
    description="FastAPI Backend for all 7 Local PostgreSQL Database Tables (ev_charging)",
    version="1.0.0"
)

# Configure CORS for React frontend (supports port 5173, 5174, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(api_router)

@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "online",
        "service": "VoltPulse EV Charging Backend",
        "database": "Local PostgreSQL (ev_charging)",
        "tables_supported": [
            "users",
            "operators",
            "stations",
            "chargers",
            "connectors",
            "reservations",
            "charging_sessions"
        ]
    }

# --- 1. USERS API ---
@app.get("/api/users", response_model=List[schemas.UserResponse], tags=["Users"])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.UserProfile).all()

@app.post("/api/users/sync", response_model=schemas.UserResponse, status_code=status.HTTP_200_OK, tags=["Users"])
def sync_user(payload: schemas.UserSync, db: Session = Depends(get_db)):
    """Sync signed up Supabase user to local PostgreSQL database"""
    print(f"📥 Received User Sync Request: email={payload.email}, uuid={payload.user_id}")
    try:
        existing_user = db.query(models.UserProfile).filter(models.UserProfile.user_id == payload.user_id).first()
        if not existing_user:
            new_user = models.UserProfile(
                user_id=payload.user_id,
                email=payload.email,
                full_name=payload.full_name,
                phone_number=payload.phone_number
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            print(f"✅ Successfully created user in local PostgreSQL: {payload.email}")
            return new_user
        print(f"ℹ️ User already exists in local PostgreSQL: {payload.email}")
        return existing_user
    except Exception as e:
        db.rollback()
        print(f"❌ Error syncing user to local PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# --- 2. OPERATORS API ---
@app.get("/api/operators", response_model=List[schemas.OperatorResponse], tags=["Operators"])
def list_operators(db: Session = Depends(get_db)):
    return db.query(models.Operator).all()

# --- 3. STATIONS API ---
@app.get("/api/stations", response_model=List[schemas.StationResponse], tags=["Stations"])
def list_stations(db: Session = Depends(get_db)):
    try:
        stations = (
            db.query(models.Station)
            .options(
                selectinload(models.Station.chargers).selectinload(models.Charger.connectors)
            )
            .all()
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Charging station data is temporarily unavailable",
        ) from exc

    return [
        station
        for station in stations
        if isinstance(station.latitude, (int, float))
        and isinstance(station.longitude, (int, float))
        and math.isfinite(station.latitude) and math.isfinite(station.longitude)
        and -90 <= station.latitude <= 90
        and -180 <= station.longitude <= 180
    ]

@app.get("/api/stations/{station_id}", response_model=schemas.StationResponse, tags=["Stations"])
def get_station(station_id: UUID, db: Session = Depends(get_db)):
    station = db.query(models.Station).filter(models.Station.station_id == station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return station

@app.post("/api/stations", response_model=schemas.StationResponse, status_code=status.HTTP_201_CREATED, tags=["Stations"])
def create_station(payload: schemas.StationCreate, db: Session = Depends(get_db)):
    station = models.Station(**payload.model_dump(exclude={"is_active"}))
    db.add(station)
    db.commit()
    db.refresh(station)
    return station

# --- 4. CHARGERS API ---
@app.get("/api/chargers", response_model=List[schemas.ChargerResponse], tags=["Chargers"])
def list_chargers(db: Session = Depends(get_db)):
    return db.query(models.Charger).all()

# --- 5. CONNECTORS API ---
@app.get("/api/connectors", response_model=List[schemas.ConnectorResponse], tags=["Connectors"])
def list_connectors(db: Session = Depends(get_db)):
    return db.query(models.Connector).all()

# --- 6. RESERVATIONS API ---
@app.get("/api/reservations/user/{user_id}", response_model=List[schemas.ReservationResponse], tags=["Reservations"])
def get_user_reservations(user_id: UUID, db: Session = Depends(get_db)):
    return db.query(models.Reservation).filter(models.Reservation.user_id == user_id).all()

@app.post("/api/reservations", response_model=schemas.ReservationResponse, status_code=status.HTTP_201_CREATED, tags=["Reservations"])
def create_reservation(payload: schemas.ReservationCreate, db: Session = Depends(get_db)):
    reservation = models.Reservation(**payload.model_dump())
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation

# --- 7. CHARGING SESSIONS API ---
@app.get("/api/sessions/user/{user_id}", response_model=List[schemas.ChargingSessionResponse], tags=["Sessions"])
def get_user_sessions(user_id: UUID, db: Session = Depends(get_db)):
    return db.query(models.ChargingSession).filter(models.ChargingSession.user_id == user_id).all()

@app.post("/api/sessions", response_model=schemas.ChargingSessionResponse, status_code=status.HTTP_201_CREATED, tags=["Sessions"])
def create_session(payload: schemas.ChargingSessionCreate, db: Session = Depends(get_db)):
    session = models.ChargingSession(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
