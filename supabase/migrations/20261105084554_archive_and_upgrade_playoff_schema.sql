SET LOCAL lock_timeout = '5s';
SET LOCAL search_path = public, pg_catalog;
LOCK TABLE public.users, public.bets, public.game_history IN ACCESS EXCLUSIVE MODE;

-- Keep the original rows, indexes, constraints and sequences for recovery.
CREATE SCHEMA playoff_legacy;
REVOKE ALL ON SCHEMA playoff_legacy FROM PUBLIC, anon, authenticated;
ALTER TABLE public.users SET SCHEMA playoff_legacy;
ALTER TABLE public.bets SET SCHEMA playoff_legacy;
ALTER TABLE public.game_history SET SCHEMA playoff_legacy;
REVOKE ALL ON ALL TABLES IN SCHEMA playoff_legacy FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA playoff_legacy FROM PUBLIC, anon, authenticated;
ALTER TABLE playoff_legacy.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE playoff_legacy.bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE playoff_legacy.game_history ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS login_attempts (
	key VARCHAR(64) NOT NULL,
	failures INTEGER NOT NULL,
	window_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (key)
);

ALTER TABLE login_attempts ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN REVOKE ALL ON TABLE login_attempts FROM anon; END IF; END $$;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN REVOKE ALL ON TABLE login_attempts FROM authenticated; END IF; END $$;

CREATE TABLE IF NOT EXISTS users (
	id SERIAL NOT NULL,
	username VARCHAR(40) NOT NULL,
	hashed_password VARCHAR(128) NOT NULL,
	balance_cents BIGINT NOT NULL,
	last_reload TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	CHECK (balance_cents >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN REVOKE ALL ON TABLE users FROM anon; END IF; END $$;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN REVOKE ALL ON TABLE users FROM authenticated; END IF; END $$;

CREATE TABLE IF NOT EXISTS auth_sessions (
	token_hash VARCHAR(64) NOT NULL,
	user_id INTEGER NOT NULL,
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions (user_id);

ALTER TABLE auth_sessions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN REVOKE ALL ON TABLE auth_sessions FROM anon; END IF; END $$;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN REVOKE ALL ON TABLE auth_sessions FROM authenticated; END IF; END $$;

CREATE TABLE IF NOT EXISTS mutations (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	request_id VARCHAR(36) NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	response_json VARCHAR NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, request_id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

ALTER TABLE mutations ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN REVOKE ALL ON TABLE mutations FROM anon; END IF; END $$;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN REVOKE ALL ON TABLE mutations FROM authenticated; END IF; END $$;

CREATE TABLE IF NOT EXISTS tournaments (
	id SERIAL NOT NULL,
	owner_id INTEGER NOT NULL,
	status VARCHAR(16) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CHECK (status IN ('active','archived')),
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_tournaments_owner_id ON tournaments (owner_id);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_tournament_per_owner ON tournaments (owner_id) WHERE status = 'active';

ALTER TABLE tournaments ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN REVOKE ALL ON TABLE tournaments FROM anon; END IF; END $$;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN REVOKE ALL ON TABLE tournaments FROM authenticated; END IF; END $$;

CREATE TABLE IF NOT EXISTS bets (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	tournament_id INTEGER NOT NULL,
	request_id VARCHAR(36) NOT NULL,
	request_fingerprint VARCHAR(64) NOT NULL,
	matchup VARCHAR(80) NOT NULL,
	game_number INTEGER NOT NULL,
	bet_type VARCHAR(32) NOT NULL,
	team_bet_on VARCHAR(80) NOT NULL,
	target_value FLOAT,
	amount_cents BIGINT NOT NULL,
	odds FLOAT NOT NULL,
	potential_win_cents BIGINT NOT NULL,
	paid_out_cents BIGINT NOT NULL,
	status VARCHAR(16) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, request_id),
	CHECK (game_number BETWEEN 0 AND 7),
	CHECK (amount_cents > 0 AND potential_win_cents >= 0 AND paid_out_cents >= 0),
	CHECK (odds >= 1),
	CHECK (status IN ('pending','won','lost','push','cancelled')),
	CHECK (bet_type IN ('moneyline','spread','over_under_points','series_winner','futures_champion')),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(tournament_id) REFERENCES tournaments (id)
);

CREATE INDEX IF NOT EXISTS ix_bets_tournament_id ON bets (tournament_id);

CREATE INDEX IF NOT EXISTS ix_bets_user_id ON bets (user_id);

ALTER TABLE bets ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN REVOKE ALL ON TABLE bets FROM anon; END IF; END $$;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN REVOKE ALL ON TABLE bets FROM authenticated; END IF; END $$;

CREATE TABLE IF NOT EXISTS game_history (
	id SERIAL NOT NULL,
	tournament_id INTEGER NOT NULL,
	series_id VARCHAR(80) NOT NULL,
	round_number INTEGER NOT NULL,
	game_number INTEGER NOT NULL,
	team1 VARCHAR(80) NOT NULL,
	team2 VARCHAR(80) NOT NULL,
	team1_pts INTEGER NOT NULL,
	team2_pts INTEGER NOT NULL,
	team1_rebounds INTEGER,
	team2_rebounds INTEGER,
	winner VARCHAR(80) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tournament_id, series_id, game_number),
	CHECK (game_number BETWEEN 1 AND 7),
	CHECK (round_number BETWEEN 1 AND 4),
	CHECK (team1_pts >= 0 AND team2_pts >= 0),
	CHECK (team1 <> team2),
	CHECK (winner = team1 OR winner = team2),
	FOREIGN KEY(tournament_id) REFERENCES tournaments (id)
);

CREATE INDEX IF NOT EXISTS ix_game_history_tournament_id ON game_history (tournament_id);

ALTER TABLE game_history ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN REVOKE ALL ON TABLE game_history FROM anon; END IF; END $$;

DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN REVOKE ALL ON TABLE game_history FROM authenticated; END IF; END $$;

REVOKE ALL ON TABLE public.users, public.bets, public.game_history, public.auth_sessions, public.login_attempts, public.tournaments, public.mutations FROM PUBLIC;

-- Start a fresh active tournament lazily. The old shared season stays archived.
-- Pending stakes are refunded because the archived season can no longer settle.
INSERT INTO public.users (id, username, hashed_password, balance_cents, last_reload)
SELECT u.id, u.username, u.hashed_password,
       round(u.balance::numeric * 100)::bigint + COALESCE(
           (SELECT sum(round(b.amount::numeric * 100)::bigint)
            FROM playoff_legacy.bets b WHERE b.user_id = u.id AND b.status = 'pending'), 0),
       u.last_reload
FROM playoff_legacy.users u;

INSERT INTO public.tournaments (owner_id, status, created_at)
SELECT id, 'archived', timezone('UTC', now())
FROM public.users;

INSERT INTO public.bets (
    id, user_id, tournament_id, request_id, request_fingerprint, matchup,
    game_number, bet_type, team_bet_on, target_value, amount_cents, odds,
    potential_win_cents, paid_out_cents, status, created_at
)
SELECT b.id, b.user_id, t.id, gen_random_uuid()::text, 'legacy-import', b.matchup,
       b.game_number, b.bet_type, b.team_bet_on, b.target_value,
       round(b.amount::numeric * 100)::bigint, b.odds,
       round(b.potential_win::numeric * 100)::bigint,
       CASE
           WHEN b.status = 'won' THEN round(b.potential_win::numeric * 100)::bigint
           WHEN b.status IN ('pending', 'push', 'cancelled') THEN round(b.amount::numeric * 100)::bigint
           ELSE 0
       END,
       CASE WHEN b.status = 'pending' THEN 'cancelled' ELSE b.status END,
       timezone('UTC', now())
FROM playoff_legacy.bets b
JOIN public.tournaments t ON t.owner_id = b.user_id;

INSERT INTO public.game_history (
    tournament_id, series_id, round_number, game_number, team1, team2,
    team1_pts, team2_pts, team1_rebounds, team2_rebounds, winner
)
SELECT t.id, g.series_id, g.round_number, g.game_number, g.team1, g.team2,
       g.team1_pts, g.team2_pts, g.team1_rebounds, g.team2_rebounds, g.winner
FROM playoff_legacy.game_history g
CROSS JOIN public.tournaments t;

SELECT setval(pg_get_serial_sequence('public.users', 'id'), COALESCE(max(id), 1), max(id) IS NOT NULL)
FROM public.users;
SELECT setval(pg_get_serial_sequence('public.bets', 'id'), COALESCE(max(id), 1), max(id) IS NOT NULL)
FROM public.bets;

DO $$
BEGIN
    IF (SELECT count(*) FROM public.users) <> (SELECT count(*) FROM playoff_legacy.users)
       OR (SELECT count(*) FROM public.bets) <> (SELECT count(*) FROM playoff_legacy.bets)
       OR (SELECT count(*) FROM public.game_history) <>
           (SELECT count(*) FROM playoff_legacy.game_history) * (SELECT count(*) FROM public.users)
    THEN
        RAISE EXCEPTION 'Legacy import counts do not match';
    END IF;
END $$;
