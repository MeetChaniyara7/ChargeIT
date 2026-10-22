"""ChargeSpot API entry point: builds the app and plugs in each feature's routes.

Run locally (from backend, with the virtual environment active):
    uvicorn app.main:app --reload --port 8000

Business logic does not live here. Each feature in app/features/ has its own
router (HTTP), service (rules) and repository (SQL).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_NAME, APP_VERSION, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.features.auth.router import api_router as auth_api_router
from app.features.auth.router import router as auth_router
from app.features.availability.router import router as availability_router
from app.features.bookings.router import router as bookings_router
from app.features.chargers.router import router as chargers_router
from app.features.charging.router import router as charging_router
from app.features.geocoding.router import router as geocoding_router
from app.features.kiosk.admin_router import router as kiosk_admin_router
from app.features.kiosk.router import router as kiosk_router
from app.features.payments.router import router as payments_router
from app.features.recommendations.router import router as recommendations_router
from app.features.search.router import router as search_router
from app.features.stations.router import router as stations_router
from app.features.vehicles.router import router as vehicles_router


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast if a required setting is missing
    setup_logging()

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="Book EV charging slots, start charging with an OTP, pay in the app.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    app.include_router(auth_router)
    app.include_router(auth_api_router)
    app.include_router(stations_router)
    app.include_router(availability_router)
    app.include_router(recommendations_router)
    app.include_router(geocoding_router)
    app.include_router(search_router)
    app.include_router(vehicles_router)
    app.include_router(bookings_router)
    app.include_router(payments_router)
    app.include_router(charging_router)
    app.include_router(chargers_router)
    app.include_router(kiosk_router)
    app.include_router(kiosk_admin_router)

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}

    return app


app = create_app()
