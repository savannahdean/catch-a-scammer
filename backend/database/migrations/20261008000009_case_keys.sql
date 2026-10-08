-- =====================================================================
-- Case keys: a case's number alone no longer opens it.
--
-- Every case gets a random access_key. Only the browser that created the case
-- is told it, and the API (server/guard.py) refuses any /api/cases/{n} request
-- that doesn't carry it. Cases that existed before this migration get a fresh
-- key nobody has, so they can't be reopened from the game.
-- =====================================================================
set search_path = public, extensions;

alter table cases add column if not exists access_key uuid not null default gen_random_uuid();
