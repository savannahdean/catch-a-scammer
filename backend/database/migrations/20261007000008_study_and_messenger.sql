-- =====================================================================
-- Research study (opt-in surveys) and the client Messenger.
--
-- STUDY: a player may opt in on the title screen. They get a pre-game survey
-- (demographics, OSINT background, a short knowledge quiz) and a post-game
-- survey (the same quiz again, plus how the game went). Questions are rows,
-- not code, so the client renders whatever is here and a researcher can add a
-- question with one INSERT. Players who don't opt in leave no study rows.
--
-- MESSENGER: the person who reported the case (the "client") is a chat
-- contact with a personality. They know what happened to them, and some of
-- them hide the embarrassing part until the player asks the right question or
-- shows proof. Every message is stored, which is research data too.
-- =====================================================================
set search_path = public, extensions;

-- ---------------------------------------------------------------------
-- Study participants and surveys
-- ---------------------------------------------------------------------
create table if not exists study_participants (
  id               uuid primary key default gen_random_uuid(),
  consent_version  text not null,
  consented_at     timestamptz not null default now(),
  pre_done_at      timestamptz,
  post_done_at     timestamptz,
  user_agent       text
);

create table if not exists survey_questions (
  key       text primary key,
  phase     text not null check (phase in ('pre','post')),
  measure   text,               -- pairs a pre and a post question that measure the same thing
  ord       smallint not null,  -- display order within the phase
  section   text not null,      -- heading the client groups questions under
  prompt    text not null,
  kind      text not null check (kind in ('number','text','longtext','choice','multi','likert')),
  options   jsonb not null default '{}',   -- choices [{value,label}] or {min,max,low,high}
  required  boolean not null default true,
  show_if   jsonb,              -- {"other_key": ["value", ...]}: only ask when that answer matches
  correct   text                -- quiz answer key; never sent to the client
);

create table if not exists survey_answers (
  participant_id uuid not null references study_participants(id) on delete cascade,
  question_key   text not null references survey_questions(key) on delete cascade,
  answer         jsonb not null,  -- number, string, or array of strings for 'multi'
  answered_at    timestamptz not null default now(),
  primary key (participant_id, question_key)
);

-- which cases a participant played (null for players outside the study)
alter table cases add column if not exists participant_id uuid references study_participants(id) on delete set null;
create index if not exists cases_participant on cases(participant_id);

-- ---------------------------------------------------------------------
-- Client personalities (tunable data, like difficulty_profiles)
-- ---------------------------------------------------------------------
create table if not exists client_profiles (
  key               text primary key,
  label             text not null,
  summary           text not null,      -- what the player is told about this client
  patience          smallint not null,  -- starting (and maximum) mood meter
  confused_cost     smallint not null,  -- an unrecognized message
  wrong_pin_cost    smallint not null,  -- pinning something the client knows is wrong
  wrong_report_cost smallint not null,  -- a returned case report
  pressure_cost     smallint not null,  -- "are you hiding something?" when they aren't, or can't be pushed
  nag_after_s       integer,            -- seconds without a reply before they chase you (null = never)
  nag_cost          smallint not null default 0,
  nag_burst         smallint not null default 1,   -- messages per chase ("blowing up your phone")
  disclosure        text not null check (disclosure in ('upfront','asked','pressed','proof')),
  volunteers        boolean not null,   -- tells the whole story in the first message
  has_theory        boolean not null default false,  -- pushes their own (wrong) theory
  difficulties      difficulty[] not null   -- where a random client can be dealt
);

insert into client_profiles values
  ('sweet', 'Super sweet',
   'Grateful, patient and upfront. Tells you everything the moment you ask.',
   100, 1, 2, 5, 0, null, 0, 1, 'upfront', true, false, '{easy}'),
  ('oversharer', 'Way too honest',
   'Answers everything and then some. The useful detail is in there, buried in things that don''t matter.',
   90, 2, 3, 8, 0, null, 0, 1, 'upfront', true, false, '{easy,medium}'),
  ('confused', 'Not tech-savvy',
   'Honest but vague, and mixes up computer words. Ask simple, specific questions.',
   90, 2, 3, 8, 2, 600, 2, 1, 'asked', false, false, '{easy,medium}'),
  ('anxious', 'Anxious',
   'Frightened and double-texts when you go quiet. Keep them updated.',
   70, 4, 6, 15, 3, 150, 2, 2, 'asked', true, false, '{medium,hard}'),
  ('busy', 'Busy executive',
   'Terse and impatient. Short answers, expects regular status updates.',
   60, 6, 8, 20, 4, 180, 4, 1, 'asked', false, false, '{medium,hard}'),
  ('skeptic', 'Know-it-all',
   'Already "knows" who did it and will push you toward their theory. They''re usually wrong.',
   65, 5, 4, 20, 4, 300, 3, 1, 'asked', false, true, '{medium,hard,expert}'),
  ('evasive', 'Embarrassed',
   'Leaves out the embarrassing part. Ask about it directly, or ask again, and it comes out.',
   70, 4, 6, 15, 3, 400, 3, 1, 'pressed', false, false, '{medium,hard,expert}'),
  ('liar', 'Liar',
   'Lies about the part they''re ashamed of and sticks to it. Only proof from your investigation makes them admit it.',
   60, 5, 8, 20, 4, 300, 3, 1, 'proof', false, false, '{hard,expert}'),
  ('rude', 'Extremely rude',
   'Hostile, short-fused and demanding. Goes quiet on the hard questions and blows up your messages if you leave them waiting.',
   35, 8, 10, 25, 6, 75, 5, 3, 'pressed', false, false, '{hard,expert}')
on conflict (key) do nothing;

-- the mood meter can only end a case from MEDIUM up
alter table difficulty_profiles add column if not exists client_can_fire boolean not null default true;
update difficulty_profiles set client_can_fire = (level <> 'easy');

-- ---------------------------------------------------------------------
-- Per-case client state, what they know, and the conversation
-- ---------------------------------------------------------------------
create table if not exists case_client (
  case_id          uuid primary key references cases(id) on delete cascade,
  personality      text not null references client_profiles(key),
  patience         smallint not null,
  max_patience     smallint not null,
  theory           text,                 -- the skeptic's wrong idea of who did it
  started_at       timestamptz,          -- when the first message was delivered
  last_activity_at timestamptz,          -- last player message or client chase
  last_reassure_at timestamptz,
  nags             integer not null default 0,
  fired_at         timestamptz
);

-- What the reporting party knows. Facts are written by each scenario.
create table if not exists case_client_facts (
  case_id     uuid not null references cases(id) on delete cascade,
  key         text not null,
  ord         smallint not null,
  topics      text[] not null,          -- intents that ask about this (see server/messenger.py)
  keywords    text[] not null default '{}',   -- extra words that point at this fact
  body        text not null,            -- the truth, first person
  secret      boolean not null default false, -- the part they may hide
  lie         text,                     -- what a liar says instead
  volunteer   boolean not null default false, -- part of the opening statement for upfront clients
  unlocks     uuid[] not null default '{}',   -- records the client hands over when they tell this
  proof       uuid[] not null default '{}',   -- records that make a liar admit it
  ask_count   smallint not null default 0,
  revealed_at timestamptz,
  primary key (case_id, key)
);

create table if not exists client_messages (
  id          bigserial primary key,
  case_id     uuid not null references cases(id) on delete cascade,
  sender      text not null check (sender in ('client','player','system')),
  body        text not null,
  intents     text[] not null default '{}',  -- what the engine understood (player messages)
  evidence_id uuid references entities(id) on delete set null,  -- a record the player showed
  cards       jsonb not null default '[]',   -- records the client handed over, as cards
  patience    smallint,                      -- the meter after this message
  created_at  timestamptz not null default now()
);
create index if not exists client_messages_case on client_messages(case_id, id);

-- payment method for card charges (what shows on a bank statement)
alter table payment_accounts drop constraint if exists payment_accounts_method_check;
alter table payment_accounts add constraint payment_accounts_method_check check (method in
  ('bank_wire','gift_card','p2p_app','money_transfer','crypto_exchange','card_merchant'));

-- tables created after the RLS loop in migration 001 need it too
do $$
declare t text;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;

-- ---------------------------------------------------------------------
-- Survey questions. Pre and post quiz items share a `measure`, so
-- v_study_learning can compare them.
-- ---------------------------------------------------------------------
insert into survey_questions(key, phase, measure, ord, section, prompt, kind, options, required, show_if, correct) values
  -- about you
  ('age', 'pre', null, 10, 'About you', 'How old are you?', 'number', '{"min":18,"max":100}', true, null, null),
  ('name', 'pre', null, 20, 'About you', 'Your name (optional: leave it blank to stay anonymous)', 'text', '{}', false, null, null),
  ('college_status', 'pre', null, 30, 'About you', 'Are you in college, or have you attended college?', 'choice',
   '[{"value":"enrolled","label":"Yes, I''m enrolled now"},{"value":"attended","label":"I attended but didn''t finish"},{"value":"graduated","label":"I graduated"},{"value":"never","label":"No, I haven''t attended college"}]',
   true, null, null),
  ('major', 'pre', null, 40, 'About you', 'What is (or was) your major?', 'text', '{}', true,
   '{"college_status":["enrolled","attended","graduated"]}', null),
  ('tech_background', 'pre', null, 50, 'About you', 'How would you describe your technology background?', 'choice',
   '[{"value":"none","label":"I avoid technology when I can"},{"value":"casual","label":"Everyday user (email, social media, browsing)"},{"value":"some","label":"Somewhat technical (took a class, tinker as a hobby)"},{"value":"student","label":"I study a tech field (CS, IT, cybersecurity, engineering)"},{"value":"professional","label":"I work in tech or IT"}]',
   true, null, null),
  ('tech_experience', 'pre', null, 60, 'About you', 'Which of these have you done? (pick all that apply)', 'multi',
   '[{"value":"code","label":"Written code"},{"value":"security_class","label":"Taken a cybersecurity class"},{"value":"it_job","label":"Worked in IT or a help desk"},{"value":"website","label":"Built a website"},{"value":"cli","label":"Used a command line / terminal"},{"value":"ctf","label":"Played a capture-the-flag (CTF) competition"},{"value":"none","label":"None of these"}]',
   false, null, null),
  ('scam_experience', 'pre', null, 70, 'About you', 'Have you, or someone close to you, been targeted by an online scam?', 'choice',
   '[{"value":"me","label":"Yes, me"},{"value":"close","label":"Yes, someone close to me"},{"value":"no","label":"No"},{"value":"skip","label":"Prefer not to say"}]',
   true, null, null),
  -- OSINT background
  ('osint_heard', 'pre', null, 110, 'Open-source intelligence (OSINT)', 'Before today, had you heard the term "OSINT" (open-source intelligence)?', 'choice',
   '[{"value":"yes","label":"Yes"},{"value":"no","label":"No"},{"value":"unsure","label":"Not sure"}]', true, null, null),
  ('osint_define', 'pre', null, 120, 'Open-source intelligence (OSINT)', 'In your own words, what is OSINT? (A guess is fine.)', 'longtext', '{}', false, null, null),
  ('osint_familiarity', 'pre', null, 130, 'Open-source intelligence (OSINT)', 'How familiar are you with OSINT techniques (WHOIS, DNS history, reverse image search, breach lookups...)?', 'likert',
   '{"min":1,"max":5,"low":"Never used any","high":"Use them regularly"}', true, null, null),
  ('osint_tools_used', 'pre', null, 140, 'Open-source intelligence (OSINT)', 'Which have you used for real before? (pick all that apply)', 'multi',
   '[{"value":"reverse_image","label":"Reverse image search"},{"value":"whois","label":"WHOIS lookup"},{"value":"breach","label":"Checking if an email was in a data breach"},{"value":"headers","label":"Reading email headers"},{"value":"dns","label":"DNS lookups"},{"value":"none","label":"None of these"}]',
   false, null, null),
  -- confidence (pre and post)
  ('conf_spot_pre', 'pre', 'conf_spot', 210, 'Confidence', 'How confident are you that you can tell a scam message from a real one?', 'likert',
   '{"min":1,"max":5,"low":"Not at all","high":"Completely"}', true, null, null),
  ('conf_investigate_pre', 'pre', 'conf_investigate', 220, 'Confidence', 'How confident are you that you could find out who is behind a scam using only public information?', 'likert',
   '{"min":1,"max":5,"low":"Not at all","high":"Completely"}', true, null, null),
  ('conf_spot_post', 'post', 'conf_spot', 210, 'Confidence', 'How confident are you now that you can tell a scam message from a real one?', 'likert',
   '{"min":1,"max":5,"low":"Not at all","high":"Completely"}', true, null, null),
  ('conf_investigate_post', 'post', 'conf_investigate', 220, 'Confidence', 'How confident are you now that you could find out who is behind a scam using only public information?', 'likert',
   '{"min":1,"max":5,"low":"Not at all","high":"Completely"}', true, null, null)
on conflict (key) do nothing;

-- the knowledge quiz, asked before and after (same wording, same options)
do $$
declare
  q record;
  ph text;
begin
  for q in select * from (values
    ('quiz_whois', 310, 'A scam domain''s WHOIS record says "REDACTED FOR PRIVACY". Where is the best place to look for who registered it?',
     '[{"value":"a","label":"Nowhere: privacy means it can''t be found"},{"value":"b","label":"Older WHOIS snapshots captured before privacy was switched on"},{"value":"c","label":"The website''s Contact page"},{"value":"d","label":"Ask the domain''s hosting company to email you"}]', 'b'),
    ('quiz_shared_ip', 320, 'A scam website''s address (IP) is shared by 300 other websites. What does that tell you?',
     '[{"value":"a","label":"All 300 websites are run by the scammer"},{"value":"b","label":"The company that owns the IP is the scammer"},{"value":"c","label":"Very little on its own: shared hosting and CDNs put many unrelated sites on one address"},{"value":"d","label":"The scam website must be safe"}]', 'c'),
    ('quiz_headers', 330, 'An email''s "From" line shows your bank''s real address. Which detail is the strongest sign it is still fake?',
     '[{"value":"a","label":"It uses the bank''s logo and colors"},{"value":"b","label":"The headers show the Return-Path / Reply-To on a different domain and DMARC failing for the bank"},{"value":"c","label":"It was sent late at night"},{"value":"d","label":"It greets you by name"}]', 'b'),
    ('quiz_photos', 340, 'A new dating profile''s photos first appeared online years earlier, on a different person''s account. What does that suggest?',
     '[{"value":"a","label":"The photos were probably stolen: a catfish"},{"value":"b","label":"The person is famous"},{"value":"c","label":"Nothing: people reuse old photos"},{"value":"d","label":"The dating site made a mistake"}]', 'a'),
    ('quiz_sources', 350, 'A low-reliability blog post blames a famous hacking group for a scam. How should an investigator treat it?',
     '[{"value":"a","label":"As proof: name that group in the report"},{"value":"b","label":"Ignore it completely"},{"value":"c","label":"As a lead to check against harder evidence like shared infrastructure or money flows"},{"value":"d","label":"Trust it if other blogs repeat it"}]', 'c'),
    ('quiz_payment', 360, 'Why do scammers so often ask to be paid in gift cards or cryptocurrency?',
     '[{"value":"a","label":"They are cheaper for the victim"},{"value":"b","label":"Those payments are hard to reverse and hard to trace to a person"},{"value":"c","label":"Banks require it for large payments"},{"value":"d","label":"It is the law for online purchases"}]', 'b')
  ) as t(measure, ord, prompt, options, correct)
  loop
    foreach ph in array array['pre','post'] loop
      insert into survey_questions(key, phase, measure, ord, section, prompt, kind, options, required, correct)
      values (q.measure || '_' || ph, ph, q.measure, q.ord, 'Quick quiz (no penalty for guessing)', q.prompt, 'choice',
              q.options::jsonb, true, q.correct)
      on conflict (key) do nothing;
    end loop;
  end loop;
end $$;

insert into survey_questions(key, phase, measure, ord, section, prompt, kind, options, required, show_if, correct) values
  ('enjoyed', 'post', null, 10, 'How it went', 'How much did you enjoy playing?', 'likert',
   '{"min":1,"max":5,"low":"Not at all","high":"A lot"}', true, null, null),
  ('learned', 'post', null, 20, 'How it went', 'How much do you feel you learned about investigating scams?', 'likert',
   '{"min":1,"max":5,"low":"Nothing","high":"A lot"}', true, null, null),
  ('difficulty_felt', 'post', null, 30, 'How it went', 'How hard was the case you played?', 'likert',
   '{"min":1,"max":5,"low":"Far too easy","high":"Far too hard"}', true, null, null),
  ('messenger_useful', 'post', null, 40, 'How it went', 'How useful was questioning the client in the Messenger?', 'likert',
   '{"min":1,"max":5,"low":"Useless","high":"Essential"}', true, null, null),
  ('client_realism', 'post', null, 50, 'How it went', 'How realistic did the client''s behavior feel?', 'likert',
   '{"min":1,"max":5,"low":"Not realistic","high":"Very realistic"}', true, null, null),
  ('most_useful_tool', 'post', null, 60, 'How it went', 'Which tool helped you most?', 'choice',
   '[{"value":"intelsearch","label":"IntelSearch"},{"value":"dns","label":"DNS History"},{"value":"whois","label":"WHOIS History"},{"value":"certs","label":"CertSearch"},{"value":"urlscan","label":"URL Scanner"},{"value":"social","label":"Social Search"},{"value":"reverseimage","label":"Reverse Image"},{"value":"phone","label":"Phone Lookup"},{"value":"payments","label":"Payments / Money Trail"},{"value":"breach","label":"Breach Lookup"},{"value":"websearch","label":"Web Search / Directory"},{"value":"messenger","label":"Messenger (the client)"},{"value":"evidencemap","label":"Evidence Map"}]',
   true, null, null),
  ('hardest_part', 'post', null, 70, 'How it went', 'What was the hardest part?', 'longtext', '{}', false, null, null),
  ('recommend', 'post', null, 80, 'How it went', 'Would you recommend this game to someone learning cybersecurity?', 'choice',
   '[{"value":"yes","label":"Yes"},{"value":"maybe","label":"Maybe"},{"value":"no","label":"No"}]', true, null, null),
  ('feedback', 'post', null, 90, 'How it went', 'Anything else you want to tell us?', 'longtext', '{}', false, null, null)
on conflict (key) do nothing;

-- ---------------------------------------------------------------------
-- Research views
-- ---------------------------------------------------------------------
-- Pre vs post on every paired measure (quiz items score 1/0, likert items keep their value).
create or replace view v_study_learning with (security_invoker = true) as
select p.id as participant_id, q.measure,
       max(case when q.phase = 'pre'  then case when q.correct is not null then (a.answer #>> '{}' = q.correct)::int
                                                 else (a.answer #>> '{}')::numeric end end) as pre_value,
       max(case when q.phase = 'post' then case when q.correct is not null then (a.answer #>> '{}' = q.correct)::int
                                                 else (a.answer #>> '{}')::numeric end end) as post_value
from study_participants p
join survey_answers a on a.participant_id = p.id
join survey_questions q on q.key = a.question_key
where q.measure is not null
group by p.id, q.measure;

-- One row per participant: background, quiz before/after, and how their cases went.
create or replace view v_study_participants with (security_invoker = true) as
select p.id as participant_id, p.consented_at, p.pre_done_at, p.post_done_at,
       (select (answer #>> '{}')::int from survey_answers where participant_id = p.id and question_key = 'age') as age,
       (select answer #>> '{}' from survey_answers where participant_id = p.id and question_key = 'college_status') as college_status,
       (select answer #>> '{}' from survey_answers where participant_id = p.id and question_key = 'major') as major,
       (select answer #>> '{}' from survey_answers where participant_id = p.id and question_key = 'tech_background') as tech_background,
       (select sum(pre_value) from v_study_learning l where l.participant_id = p.id and l.measure like 'quiz%') as quiz_pre,
       (select sum(post_value) from v_study_learning l where l.participant_id = p.id and l.measure like 'quiz%') as quiz_post,
       count(c.id) as cases_played,
       count(c.id) filter (where c.status = 'solved') as cases_solved,
       count(c.id) filter (where c.status = 'failed') as cases_lost_client,
       round(avg(c.score) filter (where c.status = 'solved')) as avg_score
from study_participants p
left join cases c on c.participant_id = p.id
group by p.id;

-- How players worked their clients: questions asked, misunderstandings, secrets uncovered.
create or replace view v_messenger_stats with (security_invoker = true) as
select c.id as case_id, c.case_code, c.scenario, c.difficulty, cc.personality, c.status,
       cc.patience as final_patience, cc.max_patience, cc.fired_at is not null as client_fired,
       cc.nags,
       (select count(*) from client_messages m where m.case_id = c.id and m.sender = 'player') as player_messages,
       (select count(*) from client_messages m where m.case_id = c.id and m.sender = 'player'
                                                 and m.intents = '{}' and m.evidence_id is null) as not_understood,
       (select count(*) from client_messages m where m.case_id = c.id and m.evidence_id is not null) as evidence_shown,
       (select count(*) from case_client_facts f where f.case_id = c.id and f.secret) as secrets,
       (select count(*) from case_client_facts f where f.case_id = c.id and f.secret and f.revealed_at is not null) as secrets_uncovered
from cases c join case_client cc on cc.case_id = c.id;
