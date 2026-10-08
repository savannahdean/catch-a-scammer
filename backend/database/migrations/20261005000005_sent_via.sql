-- 'sent_via': an email/sms was sent using a given domain (envelope/DKIM/From domain).
-- Gives a clean, walkable edge from a message to the attacker domain, instead of
-- overloading hosts_url.
set search_path = public, extensions;
alter type rel_type add value if not exists 'sent_via';
