-- 007: Payments (Razorpay, test mode).

CREATE TABLE payments (
    payment_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id          uuid NOT NULL REFERENCES bookings (booking_id) ON DELETE RESTRICT,
    session_id          uuid REFERENCES charging_sessions (session_id) ON DELETE RESTRICT,
    -- BOOKING_FEE = the ₹199 fee, ENERGY = the bill after charging,
    -- WALKIN_PREPAID = a walk-in's payment before charging.
    purpose             text NOT NULL CHECK (purpose IN ('BOOKING_FEE', 'ENERGY', 'WALKIN_PREPAID')),
    provider            text NOT NULL DEFAULT 'razorpay',
    provider_order_id   text NOT NULL UNIQUE,
    provider_payment_id text UNIQUE,
    amount              money_inr NOT NULL CHECK (amount > 0),
    currency            text NOT NULL DEFAULT 'INR',
    status              text NOT NULL DEFAULT 'CREATED'
                        CHECK (status IN ('CREATED', 'CAPTURED', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED')),
    refunded_amount     money_inr NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT payments_refund_not_more_than_paid CHECK (refunded_amount <= amount),
    -- An energy payment always belongs to a specific charging session.
    CONSTRAINT payments_energy_has_session CHECK (purpose <> 'ENERGY' OR session_id IS NOT NULL)
);

CREATE INDEX payments_booking ON payments (booking_id);

CREATE TRIGGER payments_set_updated_at BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Razorpay may send the same webhook more than once. Storing each event's ID lets the
-- API process every event exactly once.
CREATE TABLE webhook_events (
    provider_event_id text PRIMARY KEY,
    event_type        text NOT NULL,
    payload           jsonb NOT NULL,
    received_at       timestamptz NOT NULL DEFAULT now(),
    processed_at      timestamptz
);
