import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Car, Pencil, Plus, RefreshCw, Star, Trash2 } from 'lucide-react';
import { Badge, Button, Card, ConnectorIcon, EmptyState, IconButton, Sheet, SkeletonBlock, useToast } from '../../components/ui';
import { ApiError, apiFetch } from '../../lib/api';
import type { VehicleOut } from '../bookings/types';
import { useVehicles } from './useVehicles';
import { VehicleSheet } from './VehicleSheet';

export const VehiclesPage: React.FC = () => {
  const toast = useToast();
  const { vehicles, loading, error, retry } = useVehicles();
  // `editing` is a vehicle, `'new'`, or null (closed). The form remounts each time it opens.
  const [editing, setEditing] = useState<VehicleOut | 'new' | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [deleting, setDeleting] = useState<VehicleOut | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const openForm = (target: VehicleOut | 'new') => {
    setFormKey((n) => n + 1);
    setEditing(target);
  };

  const makeDefault = async (vehicle: VehicleOut) => {
    setBusyId(vehicle.vehicle_id);
    try {
      await apiFetch(`/api/me/vehicles/${vehicle.vehicle_id}`, { method: 'PATCH', body: { is_default: true } });
      toast.success(`${vehicle.nickname} is now your default vehicle`);
      retry();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not change the default.');
    } finally {
      setBusyId(null);
    }
  };

  const remove = async () => {
    if (!deleting) return;
    setBusyId(deleting.vehicle_id);
    setDeleteError(null);
    try {
      await apiFetch(`/api/me/vehicles/${deleting.vehicle_id}`, { method: 'DELETE' });
      toast.success(`${deleting.nickname} removed`);
      setDeleting(null);
      retry();
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : 'Could not remove it. Please try again.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4 px-4 py-6">
      <Link to="/profile" className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-info">
        <ArrowLeft className="size-4" aria-hidden="true" />
        Profile
      </Link>
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-display font-bold">My vehicles</h1>
        {vehicles.length > 0 && (
          <Button icon={<Plus className="size-4" aria-hidden="true" />} onClick={() => openForm('new')}>
            Add vehicle
          </Button>
        )}
      </div>
      <p className="text-sm text-muted">Your default vehicle picks the plug filter on the map and sets the battery limit on cost estimates.</p>

      {loading ? (
        <div role="status" className="space-y-3">
          <span className="sr-only">Loading your vehicles…</span>
          <SkeletonBlock className="h-24" />
          <SkeletonBlock className="h-24" />
        </div>
      ) : error && vehicles.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 p-6 text-center">
          <AlertCircle className="size-9 text-danger" aria-hidden="true" />
          <p className="text-sm text-muted">{error}</p>
          <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={retry}>
            Try again
          </Button>
        </Card>
      ) : vehicles.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Car className="size-7" />}
            title="No vehicles yet"
            text="Add your car so ChargeSpot can show only the chargers that fit its plug."
            action={
              <Button icon={<Plus className="size-4" aria-hidden="true" />} onClick={() => openForm('new')}>
                Add your first vehicle
              </Button>
            }
          />
        </Card>
      ) : (
        <ul className="space-y-3">
          {vehicles.map((vehicle) => (
            <li key={vehicle.vehicle_id}>
              <Card className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="flex flex-wrap items-center gap-2 text-base font-bold">
                      {vehicle.nickname}
                      {vehicle.is_default && (
                        <Badge tone="primary" icon={<Star className="size-3 fill-current" aria-hidden="true" />}>
                          Default
                        </Badge>
                      )}
                    </h2>
                    <p className="mt-1 text-sm">
                      <ConnectorIcon type={vehicle.connector_type} />
                    </p>
                    <p className="num mt-0.5 text-sm text-muted">{vehicle.battery_kwh} kWh battery</p>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <IconButton aria-label={`Edit ${vehicle.nickname}`} onClick={() => openForm(vehicle)}>
                      <Pencil className="size-4" aria-hidden="true" />
                    </IconButton>
                    <IconButton
                      aria-label={`Remove ${vehicle.nickname}`}
                      onClick={() => {
                        setDeleteError(null);
                        setDeleting(vehicle);
                      }}
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
                    </IconButton>
                  </div>
                </div>
                {!vehicle.is_default && (
                  <Button size="sm" variant="secondary" loading={busyId === vehicle.vehicle_id} onClick={() => void makeDefault(vehicle)}>
                    Make default
                  </Button>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}

      <VehicleSheet
        key={formKey}
        open={editing !== null}
        vehicle={editing === 'new' || editing === null ? null : editing}
        isFirst={vehicles.length === 0}
        onClose={() => setEditing(null)}
        onSaved={retry}
      />

      <Sheet
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title="Remove this vehicle?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleting(null)} disabled={busyId !== null}>
              Keep it
            </Button>
            <Button variant="danger" loading={busyId !== null} onClick={() => void remove()}>
              Remove
            </Button>
          </>
        }
      >
        <p className="text-sm">
          <span className="font-bold">{deleting?.nickname}</span> will be removed from your account. Past bookings are not affected.
          {deleting?.is_default && vehicles.length > 1 ? ' Your next vehicle becomes the default.' : ''}
        </p>
        {deleteError && (
          <p role="alert" className="mt-3 text-sm font-medium text-danger-soft">
            {deleteError}
          </p>
        )}
      </Sheet>
    </div>
  );
};
