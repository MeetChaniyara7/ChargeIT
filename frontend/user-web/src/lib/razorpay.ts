// Razorpay Checkout, loaded from Razorpay's own script (no npm package).
// docs: https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/

const SCRIPT_URL = 'https://checkout.razorpay.com/v1/checkout.js';

interface CheckoutOptions {
  key: string;
  amount: number;
  currency: string;
  order_id: string;
  name: string;
  description: string;
  prefill?: { name?: string; email?: string };
  theme?: { color: string };
  /** Seconds until Checkout closes itself. */
  timeout?: number;
  handler: (response: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => void;
  modal?: { ondismiss?: () => void; confirm_close?: boolean };
}

interface CheckoutInstance {
  open: () => void;
  on: (event: 'payment.failed', handler: (response: { error?: { description?: string; reason?: string } }) => void) => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: CheckoutOptions) => CheckoutInstance;
  }
}

/** The primary colour for Razorpay's window. Read from the design tokens so the two stay in step. */
export function primaryColour(): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim();
  return /^#[0-9a-f]{6}$/i.test(value) ? value : '#22c55e';
}

let loading: Promise<void> | null = null;

/** Loads the Checkout script once. A failed load can be tried again. */
export function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  loading ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      script.remove();
      loading = null; // allow a retry
      reject(new Error("Couldn't load the payment window. Check your connection and try again."));
    };
    document.head.appendChild(script);
  });
  return loading;
}

export interface PaymentResult {
  /** paid = the browser says it went through (the server still has to verify it); failed = the payment was declined; closed = the driver closed the window. */
  status: 'paid' | 'failed' | 'closed';
  payload?: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string };
  message?: string;
}

export interface CheckoutRequest {
  keyId: string;
  orderId: string;
  amountPaise: number;
  currency: string;
  description: string;
  timeoutSeconds: number;
  prefill?: { name?: string; email?: string };
  /** The primary colour, e.g. "#22c55e". */
  color: string;
}

/** Opens Checkout and resolves once, whichever way it ends. */
export async function openCheckout(request: CheckoutRequest): Promise<PaymentResult> {
  await loadCheckout();
  const Razorpay = window.Razorpay;
  if (!Razorpay) throw new Error("Couldn't load the payment window.");

  return new Promise<PaymentResult>((resolve) => {
    let finished = false;
    let lastFailure: string | undefined;
    const finish = (result: PaymentResult) => {
      if (finished) return;
      finished = true;
      resolve(result);
    };
    const checkout = new Razorpay({
      key: request.keyId,
      amount: request.amountPaise,
      currency: request.currency,
      order_id: request.orderId,
      name: 'ChargeSpot',
      description: request.description,
      prefill: request.prefill,
      theme: { color: request.color },
      timeout: request.timeoutSeconds,
      handler: (payload) => finish({ status: 'paid', payload }),
      // A failed attempt does not close Checkout (the driver can try another method there), so a close that
      // follows a failure is reported as a failed payment rather than a plain close.
      modal: { ondismiss: () => finish(lastFailure ? { status: 'failed', message: lastFailure } : { status: 'closed' }) },
    });
    checkout.on('payment.failed', (response) => {
      lastFailure = response.error?.description ?? response.error?.reason ?? 'The payment was declined.';
    });
    checkout.open();
  });
}
