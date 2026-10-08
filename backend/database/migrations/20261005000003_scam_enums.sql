-- =====================================================================
-- Multi-scenario expansion, part 1: new enum values.
-- Kept in its own file because Postgres can't use a freshly added enum
-- value inside the same transaction that added it.
-- =====================================================================
set search_path = public, extensions;

alter type entity_kind add value if not exists 'image';
alter type entity_kind add value if not exists 'social_post';
alter type entity_kind add value if not exists 'document';
alter type entity_kind add value if not exists 'audio_recording';
alter type entity_kind add value if not exists 'sms_message';
alter type entity_kind add value if not exists 'payment_account';
alter type entity_kind add value if not exists 'lure_template';
alter type entity_kind add value if not exists 'complaint';

alter type rel_type add value if not exists 'follows';            -- persona -> persona
alter type rel_type add value if not exists 'posted';             -- persona -> social_post
alter type rel_type add value if not exists 'replied_to';         -- social_post -> social_post
alter type rel_type add value if not exists 'messaged';           -- persona -> persona (DM / chat)
alter type rel_type add value if not exists 'uses_image';         -- persona/url_scan -> image
alter type rel_type add value if not exists 'image_seen_at';      -- image -> persona/url (reverse image hit)
alter type rel_type add value if not exists 'attached';           -- email_message -> document
alter type rel_type add value if not exists 'pays_to';            -- message/document/persona -> payment_account/crypto_wallet
alter type rel_type add value if not exists 'transfers_to';       -- wallet/account -> wallet/account (money trail)
alter type rel_type add value if not exists 'voice_cloned_from';  -- audio_recording -> audio_recording (public source)
alter type rel_type add value if not exists 'impersonates';       -- persona/email/audio/domain -> person/organization
alter type rel_type add value if not exists 'variant_of';         -- lure_template -> lure_template
alter type rel_type add value if not exists 'sent_from_number';   -- sms/audio -> phone
alter type rel_type add value if not exists 'calls_back_to';      -- audio/sms/page -> phone
alter type rel_type add value if not exists 'mx_record';          -- domain -> ip (mail server)
alter type rel_type add value if not exists 'recruited';          -- persona -> persona (mule recruitment)
alter type rel_type add value if not exists 'derived_from';       -- document/email -> document/web_article (where the attacker got the info)
alter type rel_type add value if not exists 'uses_template';      -- email/sms/url_scan -> lure_template
