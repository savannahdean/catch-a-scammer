-- 'serves_ad': a website displayed an ad that led somewhere (adult-site malvertising).
-- Kept in its own file because Postgres can't use a freshly added enum value
-- inside the same transaction that added it.
set search_path = public, extensions;
alter type rel_type add value if not exists 'serves_ad';     -- domain -> url (an ad slot on that site)
