"""/api/me/vehicles: the signed-in user's vehicles."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.vehicles import service
from app.features.vehicles.schemas import VehicleIn, VehicleOut, VehicleUpdate

router = APIRouter(prefix="/api/me/vehicles", tags=["Vehicles"])


@router.get("", response_model=list[VehicleOut])
def list_vehicles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.list_vehicles(db, user.user_id)


@router.post("", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
def add_vehicle(data: VehicleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.create(db, user.user_id, data)


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def change_vehicle(vehicle_id: UUID, data: VehicleUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.update_vehicle(db, user.user_id, vehicle_id, data)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.delete(db, user.user_id, vehicle_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
