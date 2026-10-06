-- Drops only this project's objects (leaves anything else in the database alone).
set search_path = public, extensions;
drop view if exists v_player_paths cascade;
drop table if exists compat_case_ids, compat_entity_ids, _migrations, scenarios, images, social_posts, documents, audio_recordings, sms_messages,
  phone_numbers, payment_accounts, lure_templates, complaints cascade;
drop table if exists submissions, query_log, case_evidence, case_hints, case_ground_truth, case_entities,
  entity_relationships, web_articles, breach_records, breaches, crypto_wallets, organizations, persons,
  personas, actor_aliases, threat_actors, campaigns, malware_samples, malware_families, email_messages,
  email_addresses, tracking_ids, url_scans, urls, certificates, whois_records, domains, nameservers,
  registrars, ip_addresses, asns, hosting_providers, entities, cases, sources, difficulty_profiles cascade;
drop function if exists visible_entities, visible_edges, intel_search, pdns, ct_search, pivot, neighbors,
  reachable_evidence, case_is_solvable, reverse_image, money_trail cascade;
drop type if exists entity_kind, verdict, rel_type, case_role, difficulty, case_status cascade;
