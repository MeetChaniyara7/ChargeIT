import { useCallback, useRef, useState } from 'react';
import { formatINR } from '@chargespot/shared';
import { ApiError, apiFetch } from '../../lib/api';
import { openCheckout, primaryColour } from '../../lib/razorpay';
import type { PaymentResult } from '../../lib/razorpay';
import { useAuth } from '../auth/AuthContext';
import type { VerifyRequest } from '../bookings/types';
import type { EnergyOrder, LiveSession } from './types';

export type BillProblem =
  | { kind: 'payment'; message: string }
  | { kind: 'verify'; message: string; payload: VerifyRequest }
  | { kind: 'other'; message: string };

/**
 * Paying the energy bill of a finished session: ask the server for the order (the amount is the server's bill),
 * open Razorpay Checkout, then send the result back for the server to verify. The browser's word alone pays nothing.
 *
 *   paid      the server verified it: `onPaid` gets the updated session
 *   failed    the payment was declined: a message, and the driver can try again
 *   dismissed the driver closed the window: nothing is wrong, nothing is shown
 */
export function useBillPayment(sessionId: string, onPaid: (session: LiveSession) => void) {
  const { user } = useAuth();
  const [paying, setPaying] = useState(false);
  const [problem, setProblem] = useState<BillProblem | null>(null);
  const busy = useRef(false); // a second tap while Checkout is opening must not start a second payment

  const verify = useCallback(
    async (payload: VerifyRequest) => {
      try {
        const session = await apiFetch<LiveSession>(`/api/me/sessions/${encodeURIComponent(sessionId)}/pay/verify`, { method: 'POST', body: payload });
        setProblem(null);
        onPaid(session);
      } catch (error) {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.code !== 'NETWORK_ERROR') {
          setProblem({ kind: 'other', message: error.message });
        } else {
          // The money may have been taken, so keep the proof and let the driver check again.
          setProblem({ kind: 'verify', payload, message: "We couldn't confirm your payment yet. If money was taken, your bill will show as paid soon: check again." });
        }
      }
    },
    [sessionId, onPaid],
  );

  const pay = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setPaying(true);
    setProblem(null);
    try {
      const order = await apiFetch<EnergyOrder>(`/api/me/sessions/${encodeURIComponent(sessionId)}/pay`, { method: 'POST' });
      const result: PaymentResult = await openCheckout({
        keyId: order.key_id,
        orderId: order.order_id,
        amountPaise: order.amount_paise,
        currency: order.currency,
        description: `Charging bill ${formatINR(order.amount)}`,
        timeoutSeconds: 15 * 60,
        prefill: { name: user?.full_name ?? undefined, email: user?.email },
        color: primaryColour(),
      });
      if (result.status === 'paid' && result.payload) await verify(result.payload);
      else if (result.status === 'failed') setProblem({ kind: 'payment', message: result.message ?? 'The payment was declined.' });
    } catch (error) {
      setProblem({ kind: 'other', message: error instanceof Error ? error.message : 'Something went wrong. Please try again.' });
    } finally {
      busy.current = false;
      setPaying(false);
    }
  }, [sessionId, user, verify]);

  const checkAgain = useCallback(async () => {
    if (problem?.kind !== 'verify') return;
    setPaying(true);
    await verify(problem.payload);
    setPaying(false);
  }, [problem, verify]);

  return { pay, checkAgain, paying, problem };
}
