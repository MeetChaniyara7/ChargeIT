-- 016: A record of what admins did (Phase 7, admin area).
--
-- Every change an admin makes through the admin pages (a role, a kiosk key, a charger taken out of service, a station
-- edited, an operator added) is written here, with who did it. It is the audit trail the jury can be shown next to
-- booking_events. The admin's email is copied in so the record stays readable even if the account is deleted later.

CREATE TABLE admin_actions (
    action_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    admin_user_id uuid REFERENCES users (user_id) ON DELETE SET NULL,
    admin_email   text NOT NULL,
    action        text NOT NULL,        -- a short code, e.g. USER_ROLE_CHANGED
    target        text,                 -- what it was done to, in words, e.g. "riya@example.com"
    details       jsonb NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX admin_actions_time ON admin_actions (created_at DESC);

ALTER TABLE admin_actions ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE admin_actions IS 'What admins changed, and who did it (role changes, kiosk keys, out of service, edits).';
