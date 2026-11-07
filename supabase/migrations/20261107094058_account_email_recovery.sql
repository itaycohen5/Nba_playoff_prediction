-- Additive migration: existing users, balances, sessions and bets are preserved.
CREATE TABLE public.account_emails (
    user_id INTEGER PRIMARY KEY REFERENCES public.users(id),
    email VARCHAR(254) NOT NULL,
    verified_at TIMESTAMP WITHOUT TIME ZONE,
    verification_hash VARCHAR(64) UNIQUE,
    verification_expires_at TIMESTAMP WITHOUT TIME ZONE
);
CREATE INDEX ix_account_emails_email ON public.account_emails(email);
CREATE UNIQUE INDEX one_verified_account_per_email ON public.account_emails(email)
    WHERE verified_at IS NOT NULL;
ALTER TABLE public.account_emails ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.account_emails FROM PUBLIC, anon, authenticated;
