import React, { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, MapPin, RefreshCw, TimerOff } from 'lucide-react';
import { formatINR, formatTimeIST } from '@chargespot/shared';
import { Button, buttonClasses, Card, Money, SkeletonBlock, SkeletonLine, useToast } from '../../components/ui';
import { ApiError, apiFetch } from '../../lib/api';
import { openCheckout, primaryColour } from '../../lib/razorpay';
import type { PaymentResult } from '../../lib/razorpay';
import { useAuth } from '../auth/AuthContext';
import { formatSlot } from './format';
import type { OrderOut, TicketState, VerifyOut, VerifyRequest } from './types';
import { useBooking } from './useBookings';
import { HoldRing } from './HoldRing';
import { useHoldCountdown } from './useHoldCountdown';

type Problem =
  | { kind: 'payment'; message: string }
  | { kind: 'verify'; message: string; payload: VerifyRequest }
  | { kind: 'other'; message: string };

/**
 * Hold & pay: the slot is held for 5 minutes while the driver pays the ₹199 booking fee.
 * The countdown comes from the server's numbers; when it reaches zero the page asks the server again.
 */
export const HoldPage: React.FC = () => {
  const { bookingId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { user } = useAuth();
  const query = useBooking(bookingId);
  const { secondsLeft, fraction } = useHoldCountdown(query.data);

  const [paying, setPaying] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [lateRefund, setLateRefund] = useState<number | null>(null);

  // When the countdown reaches zero, ask the server: it decides whether the hold really ran out.
  const askedAtZero = useRef(false);
  const leaving = useRef(false); // set when we are moving on to the ticket
  const retry = query.retry;
  useEffect(() => {
    if (secondsLeft === 0 && !askedAtZero.current) {
      askedAtZero.current = true;
      retry();
    }
    if (secondsLeft !== null && secondsLeft > 0) askedAtZero.current = false;
  }, [secondsLeft, retry]);

  const booking = query.data?.booking;

  const afterVerify = (result: VerifyOut) => {
    if (result.outcome === 'REFUNDED_LATE') {
      setLateRefund(result.refund_amount);
      return;
    }
    const state: TicketState = { otp: result.otp ?? undefined };
    leaving.current = true;
    navigate(`/tickets/${result.booking.booking_id}`, { replace: true, state });
  };

  const verify = async (payload: VerifyRequest) => {
    try {
      afterVerify(await apiFetch<VerifyOut>('/api/payments/verify', { method: 'POST', body: payload }));
    } catch (error) {
      if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.code !== 'NETWORK_ERROR') {
        setProblem({ kind: 'other', message: error.message });
      } else {
        // The money may have been taken, so keep the proof and let the driver check again.
        setProblem({ kind: 'verify', payload, message: "We couldn't confirm your payment yet. If money was taken, your slot is still safe: check again." });
      }
    }
  };

  const payingRef = useRef(false); // a fast double tap must not start two payments
  const pay = async () => {
    if (!bookingId || payingRef.current) return;
    payingRef.current = true;
    setPaying(true);
    setProblem(null);
    try {
      const order = await apiFetch<OrderOut>('/api/payments/orders', { method: 'POST', body: { booking_id: bookingId } });
      const result: PaymentResult = await openCheckout({
        keyId: order.key_id,
        orderId: order.order_id,
        amountPaise: order.amount_paise,
        currency: order.currency,
        description: `Booking fee for ${query.data?.booking.station.name ?? 'your slot'}`,
        timeoutSeconds: order.checkout_timeout_seconds,
        prefill: { name: user?.full_name ?? undefined, email: user?.email },
        color: primaryColour(),
      });
      if (result.status === 'paid' && result.payload) {
        await verify(result.payload);
      } else if (result.status === 'failed') {
        setProblem({ kind: 'payment', message: result.message ?? 'The payment was declined.' });
      } else {
        toast.info(`Payment window closed. Your slot is held until ${formatTimeIST(order.hold_expires_at)}.`);
      }
    } catch (error) {
      if (error instanceof ApiError && error.code === 'HOLD_EXPIRED') {
        retry();
      } else {
        setProblem({ kind: 'other', message: error instanceof Error ? error.message : 'Something went wrong. Please try again.' });
      }
    } finally {
      payingRef.current = false;
      setPaying(false);
      if (!leaving.current) retry(); // the server may have confirmed it (e.g. through the payment webhook) while Checkout was open
    }
  };

  const release = async () => {
    if (!bookingId || !booking) return;
    setCancelling(true);
    try {
      await apiFetch(`/api/bookings/${bookingId}/cancel`, { method: 'POST' });
      toast.success('Slot released');
      navigate(`/stations/${booking.station.station_id}`, { replace: true });
    } catch (error) {
      setProblem({ kind: 'other', message: error instanceof Error ? error.message : 'Could not release the slot.' });
      setCancelling(false);
    }
  };

  if (query.loading) {
    return (
      <div className="mx-auto max-w-md space-y-4 px-4 py-6" role="status">
        <span className="sr-only">Loading your booking…</span>
        <SkeletonBlock className="mx-auto size-40 rounded-full" />
        <SkeletonLine className="h-6 w-2/3" />
        <SkeletonBlock className="h-40" />
      </div>
    );
  }

  if (query.error && !booking) {
    const notFound = /not found|404/i.test(query.error);
    return (
      <div className="mx-auto max-w-md px-4 py-6">
        <Card className="flex flex-col items-center gap-3 p-6 text-center">
          <AlertCircle className="size-9 text-danger" aria-hidden="true" />
          <h1 className="text-base font-bold">{notFound ? "We couldn't find that booking" : "Couldn't load this booking"}</h1>
          <p className="text-sm text-muted">{query.error}</p>
          {notFound ? (
            <Link to="/bookings" className={buttonClasses()}>
              My bookings
            </Link>
          ) : (
            <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={query.retry}>
              Try again
            </Button>
          )}
        </Card>
      </div>
    );
  }
  if (!booking) return null;

  // Paid (maybe through the webhook while this page was open): go to the ticket.
  if (booking.status === 'CONFIRMED' || booking.status === 'ACTIVE') return <Navigate to={`/tickets/${booking.booking_id}`} replace />;

  if (lateRefund !== null) {
    return (
      <div className="mx-auto max-w-md px-4 py-6">
        <Card className="flex flex-col items-center gap-3 p-6 text-center" role="alert">
          <AlertCircle className="size-9 text-warning" aria-hidden="true" />
          <h1 className="text-xl font-bold">Your payment arrived too late</h1>
          <p className="text-sm text-muted">
            The hold ran out and the slot is no longer free. The booking fee of {formatINR(lateRefund)} is being refunded in full.
          </p>
          <Link to={`/stations/${booking.station.station_id}`} className={buttonClasses()}>
            Choose another time
          </Link>
        </Card>
      </div>
    );
  }

  if (booking.status !== 'HELD') {
    const cancelled = booking.status === 'CANCELLED';
    return (
      <div className="mx-auto max-w-md px-4 py-6">
        <Card className="flex flex-col items-center gap-3 p-6 text-center" role="status">
          <TimerOff className="size-9 text-warning" aria-hidden="true" />
          <h1 className="text-xl font-bold">{cancelled ? 'Slot released' : 'Hold expired, slot released'}</h1>
          <p className="text-sm text-muted">
            {cancelled ? 'You cancelled this hold and nothing was charged.' : 'The 5 minutes ran out before payment, and nothing was charged.'} Your picked blocks are
            still selected, so you can try again.
          </p>
          <Link to={`/stations/${booking.station.station_id}`} className={buttonClasses()}>
            Back to {booking.station.name}
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md space-y-5 px-4 py-6">
      <h1 className="text-center text-xl font-bold">Hold &amp; pay</h1>
      <HoldRing secondsLeft={secondsLeft ?? 0} fraction={fraction} />

      <Card className="space-y-3 p-4">
        <div>
          <p className="text-base font-bold">{booking.station.name}</p>
          <p className="mt-0.5 flex items-start gap-1.5 text-sm text-muted">
            <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {booking.station.address}
          </p>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 border-t border-border pt-3 text-sm">
          <dt className="text-muted">Charger</dt>
          <dd className="text-right font-medium">
            {booking.charger.label}
            {booking.charger.power_kw ? ` · ${booking.charger.power_kw} kW` : ''}
          </dd>
          <dt className="text-muted">When</dt>
          <dd className="num text-right font-medium">{formatSlot(booking.start, booking.end)}</dd>
          <dt className="text-muted">Booking fee</dt>
          <dd className="text-right text-base font-bold">
            <Money value={booking.booking_fee} />
          </dd>
        </dl>
        <p className="text-xs text-muted">The fee holds your slot. You pay for the energy you use after charging. Cancel at least 2 hours ahead for a full refund.</p>
      </Card>

      {problem && (
        <div role="alert" className="rounded-card border border-danger/40 bg-danger/10 p-4 text-sm">
          <p className="flex items-center gap-2 font-bold text-danger-soft">
            <AlertCircle className="size-4" aria-hidden="true" />
            {problem.kind === 'payment' ? "Payment didn't go through" : problem.kind === 'verify' ? 'Waiting to confirm your payment' : 'Something went wrong'}
          </p>
          <p className="mt-1 text-muted">
            {problem.message}
            {problem.kind === 'payment' && ' Your slot is still held, so you can try again.'}
          </p>
          {problem.kind === 'verify' && (
            <Button className="mt-3" variant="secondary" size="sm" onClick={() => void verify(problem.payload)}>
              Check again
            </Button>
          )}
        </div>
      )}

      <div className="space-y-2">
        <Button size="lg" fullWidth loading={paying} disabled={cancelling || secondsLeft === 0} onClick={() => void pay()}>
          {problem?.kind === 'payment' ? 'Try again' : <>Pay {formatINR(booking.booking_fee)}</>}
        </Button>
        <Button variant="ghost" fullWidth loading={cancelling} disabled={paying} onClick={() => void release()}>
          Release this slot
        </Button>
      </div>
      <p className="flex items-center justify-center gap-1.5 text-center text-xs text-muted">
        <CheckCircle2 className="size-3.5" aria-hidden="true" />
        Test mode: use UPI success@razorpay. No real money moves.
      </p>
    </div>
  );
};
