-- Demo parent + children + sample activity for local dashboard.
-- Password for parent@thinko.local: password123
-- Fixed UUIDs so root .env CHILD_ID can point at the seeded child (Alex).

create extension if not exists "pgcrypto";

-- Auth user (local only; enable_confirmations = false in config.toml)
-- GoTrue requires token/change columns to be '' not NULL or login returns
-- "Database error querying schema".
insert into auth.users (
  instance_id,
  id,
  aud,
  role,
  email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at,
  updated_at,
  confirmation_token,
  recovery_token,
  email_change_token_new,
  email_change_token_current,
  reauthentication_token,
  phone_change_token,
  email_change,
  phone,
  phone_change
) values (
  '00000000-0000-0000-0000-000000000000',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'authenticated',
  'authenticated',
  'parent@thinko.local',
  crypt('password123', gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Demo Parent"}'::jsonb,
  now(),
  now(),
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  '',
  ''
) on conflict (id) do nothing;

-- identity for email login
insert into auth.identities (
  id,
  user_id,
  identity_data,
  provider,
  provider_id,
  last_sign_in_at,
  created_at,
  updated_at
) values (
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  jsonb_build_object('sub', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'email', 'parent@thinko.local'),
  'email',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  now(),
  now(),
  now()
) on conflict (id) do nothing;

-- Profile may already exist via trigger; ensure it
insert into public.profiles (id, role, display_name)
values ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'parent', 'Demo Parent')
on conflict (id) do update set display_name = excluded.display_name;

-- Two demo children
insert into public.children (id, parent_id, display_name) values
  (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'Alex'
  ),
  (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'Sam'
  )
on conflict (id) do nothing;

insert into public.devices (id, child_id, label) values
  (
    'cccccccc-cccc-cccc-cccc-cccccccccccc',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'Alex desk mic'
  ),
  (
    'cccccccc-cccc-cccc-cccc-ccccccccccc2',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
    'Sam bedroom mic'
  )
on conflict (id) do nothing;

insert into public.child_stats (
  child_id, current_streak_days, longest_streak_days, sessions_completed, last_session_on
) values
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 5, 9, 12, current_date),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2', 2, 4, 5, current_date - 1)
on conflict (child_id) do update set
  current_streak_days = excluded.current_streak_days,
  longest_streak_days = excluded.longest_streak_days,
  sessions_completed = excluded.sessions_completed,
  last_session_on = excluded.last_session_on;

-- ---------------------------------------------------------------------------
-- Alex: a week of STEM voice sessions
-- ---------------------------------------------------------------------------

insert into public.sessions (
  id, child_id, started_at, ended_at, turn_count, primary_mode, topic, duration_seconds
) values
  -- yesterday: fractions walkthrough
  (
    'dddddddd-dddd-dddd-dddd-ddddddddddd1',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    now() - interval '1 day',
    now() - interval '1 day' + interval '14 minutes',
    8,
    'walkthrough',
    'fractions',
    840
  ),
  -- 2 days ago: quiz mode decimals
  (
    'dddddddd-dddd-dddd-dddd-ddddddddddd2',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    now() - interval '2 days',
    now() - interval '2 days' + interval '11 minutes',
    6,
    'quiz',
    'decimals',
    660
  ),
  -- 3 days ago: area
  (
    'dddddddd-dddd-dddd-dddd-ddddddddddd3',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    now() - interval '3 days',
    now() - interval '3 days' + interval '18 minutes',
    10,
    'walkthrough',
    'area',
    1080
  ),
  -- 4 days ago: teach-back on fractions
  (
    'dddddddd-dddd-dddd-dddd-ddddddddddd4',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    now() - interval '4 days',
    now() - interval '4 days' + interval '9 minutes',
    6,
    'teach_back',
    'fractions',
    540
  ),
  -- 5 days ago: chemistry intro
  (
    'dddddddd-dddd-dddd-dddd-ddddddddddd5',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    now() - interval '5 days',
    now() - interval '5 days' + interval '16 minutes',
    8,
    'walkthrough',
    'chemistry',
    960
  ),
  -- today morning: quick algebra
  (
    'dddddddd-dddd-dddd-dddd-ddddddddddd6',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    now() - interval '3 hours',
    now() - interval '3 hours' + interval '12 minutes',
    7,
    'walkthrough',
    'algebra',
    720
  )
on conflict (id) do nothing;

-- Sam sessions
insert into public.sessions (
  id, child_id, started_at, ended_at, turn_count, primary_mode, topic, duration_seconds
) values
  (
    'dddddddd-dddd-dddd-dddd-dddddddddde1',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
    now() - interval '1 day',
    now() - interval '1 day' + interval '10 minutes',
    5,
    'walkthrough',
    'multiplication',
    600
  ),
  (
    'dddddddd-dddd-dddd-dddd-dddddddddde2',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
    now() - interval '3 days',
    now() - interval '3 days' + interval '8 minutes',
    4,
    'quiz',
    'addition',
    480
  )
on conflict (id) do nothing;

-- Turns: fractions (session 1)
insert into public.turns (session_id, idx, role, content, mode, topic) values
  ('dddddddd-dddd-dddd-dddd-ddddddddddd1', 0, 'user',
   'Can you help me with one half plus one fourth?', 'walkthrough', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd1', 1, 'assistant',
   'Sure! What do both fractions need before we can add them?', 'walkthrough', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd1', 2, 'user',
   'A common denominator?', 'walkthrough', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd1', 3, 'assistant',
   'Exactly. What common denominator works for 2 and 4?', 'walkthrough', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd1', 4, 'user',
   'Four!', 'walkthrough', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd1', 5, 'assistant',
   'Nice. So one half becomes two fourths. Now add two fourths and one fourth.', 'walkthrough', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd1', 6, 'user',
   'Three fourths.', 'walkthrough', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd1', 7, 'assistant',
   'You got it — three fourths. Want another one?', 'walkthrough', 'fractions')
on conflict (session_id, idx) do nothing;

-- Turns: decimals quiz
insert into public.turns (session_id, idx, role, content, mode, topic) values
  ('dddddddd-dddd-dddd-dddd-ddddddddddd2', 0, 'assistant',
   'Quiz mode: 0.5 plus 0.25 equals 0.8. Spot the mistake?', 'quiz', 'decimals'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd2', 1, 'user',
   'Um… is it wrong because it should be 0.75?', 'quiz', 'decimals'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd2', 2, 'assistant',
   'Yes! Half plus a quarter is three quarters, or 0.75. What tipped you off?', 'quiz', 'decimals'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd2', 3, 'user',
   'Because 25 and 50 make 75, not 80.', 'quiz', 'decimals'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd2', 4, 'assistant',
   'Sharp listening. Ready for another planted mistake?', 'quiz', 'decimals'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd2', 5, 'user',
   'Yeah, quiz me again.', 'quiz', 'decimals')
on conflict (session_id, idx) do nothing;

-- Turns: area
insert into public.turns (session_id, idx, role, content, mode, topic) values
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 0, 'user',
   'How do I find the area of a rectangle that is 5 by 3?', 'walkthrough', 'area'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 1, 'assistant',
   'What operation combines length and width for area?', 'walkthrough', 'area'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 2, 'user',
   'Multiply them?', 'walkthrough', 'area'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 3, 'assistant',
   'Right — 5 times 3. What do you get?', 'walkthrough', 'area'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 4, 'user',
   'Fifteen.', 'walkthrough', 'area'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 5, 'assistant',
   'Fifteen square units. If the units are centimeters, how would you say that?', 'walkthrough', 'area'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 6, 'user',
   'Fifteen square centimeters.', 'walkthrough', 'area'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 7, 'assistant',
   'Perfect. Want to try a square that is 4 on each side?', 'walkthrough', 'area'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 8, 'user',
   'That would be 16.', 'walkthrough', 'area'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd3', 9, 'assistant',
   'Yes — 4 times 4 is 16 square units.', 'walkthrough', 'area')
on conflict (session_id, idx) do nothing;

-- Turns: teach-back fractions
insert into public.turns (session_id, idx, role, content, mode, topic) values
  ('dddddddd-dddd-dddd-dddd-ddddddddddd4', 0, 'user',
   'Let me teach you about fractions.', 'teach_back', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd4', 1, 'assistant',
   'I am listening. What is a fraction?', 'teach_back', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd4', 2, 'user',
   'It is a part of a whole, like slices of pizza.', 'teach_back', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd4', 3, 'assistant',
   'Okay, so if I eat 2 of 8 slices, what fraction did I eat?', 'teach_back', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd4', 4, 'user',
   'Two eighths, which is the same as one fourth.', 'teach_back', 'fractions'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd4', 5, 'assistant',
   'Clear explanation — you even simplified it. Nice teaching.', 'teach_back', 'fractions')
on conflict (session_id, idx) do nothing;

-- Turns: chemistry
insert into public.turns (session_id, idx, role, content, mode, topic) values
  ('dddddddd-dddd-dddd-dddd-ddddddddddd5', 0, 'user',
   'What does H 2 O mean?', 'walkthrough', 'chemistry'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd5', 1, 'assistant',
   'What do the letters stand for in that formula?', 'walkthrough', 'chemistry'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd5', 2, 'user',
   'H is hydrogen and O is oxygen.', 'walkthrough', 'chemistry'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd5', 3, 'assistant',
   'And the 2?', 'walkthrough', 'chemistry'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd5', 4, 'user',
   'Two hydrogen atoms with one oxygen.', 'walkthrough', 'chemistry'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd5', 5, 'assistant',
   'That is water. What everyday place do you see H 2 O?', 'walkthrough', 'chemistry'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd5', 6, 'user',
   'In my water bottle!', 'walkthrough', 'chemistry'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd5', 7, 'assistant',
   'Exactly. Ready to look at carbon dioxide next?', 'walkthrough', 'chemistry')
on conflict (session_id, idx) do nothing;

-- Turns: algebra today
insert into public.turns (session_id, idx, role, content, mode, topic) values
  ('dddddddd-dddd-dddd-dddd-ddddddddddd6', 0, 'user',
   'Solve for x: x plus 3 equals 10.', 'walkthrough', 'algebra'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd6', 1, 'assistant',
   'What can you do to both sides to isolate x?', 'walkthrough', 'algebra'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd6', 2, 'user',
   'Subtract 3?', 'walkthrough', 'algebra'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd6', 3, 'assistant',
   'Do that. What is left?', 'walkthrough', 'algebra'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd6', 4, 'user',
   'x equals 7.', 'walkthrough', 'algebra'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd6', 5, 'assistant',
   'Check: 7 plus 3 is 10. It works. Want a slightly harder one?', 'walkthrough', 'algebra'),
  ('dddddddd-dddd-dddd-dddd-ddddddddddd6', 6, 'user',
   'Yes please.', 'walkthrough', 'algebra')
on conflict (session_id, idx) do nothing;

-- Sam turns
insert into public.turns (session_id, idx, role, content, mode, topic) values
  ('dddddddd-dddd-dddd-dddd-dddddddddde1', 0, 'user',
   'What is 6 times 7?', 'walkthrough', 'multiplication'),
  ('dddddddd-dddd-dddd-dddd-dddddddddde1', 1, 'assistant',
   'How would you break that up if you know 6 times 5?', 'walkthrough', 'multiplication'),
  ('dddddddd-dddd-dddd-dddd-dddddddddde1', 2, 'user',
   '6 times 5 is 30, plus another 6 and 6… 42?', 'walkthrough', 'multiplication'),
  ('dddddddd-dddd-dddd-dddd-dddddddddde1', 3, 'assistant',
   'Yes — 42. Nice strategy.', 'walkthrough', 'multiplication'),
  ('dddddddd-dddd-dddd-dddd-dddddddddde1', 4, 'user',
   'Thanks Lil-Vro!', 'walkthrough', 'multiplication'),
  ('dddddddd-dddd-dddd-dddd-dddddddddde2', 0, 'assistant',
   'Quiz: 9 plus 6 equals 16. Find the mistake.', 'quiz', 'addition'),
  ('dddddddd-dddd-dddd-dddd-dddddddddde2', 1, 'user',
   'It should be 15!', 'quiz', 'addition'),
  ('dddddddd-dddd-dddd-dddd-dddddddddde2', 2, 'assistant',
   'Caught it. 9 plus 6 is 15.', 'quiz', 'addition'),
  ('dddddddd-dddd-dddd-dddd-dddddddddde2', 3, 'user',
   'That was easy.', 'quiz', 'addition')
on conflict (session_id, idx) do nothing;

-- Mastery for Alex
insert into public.mastery_scores (child_id, topic, score, updated_at) values
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'fractions', 0.78, now() - interval '1 day'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'decimals', 0.64, now() - interval '2 days'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'area', 0.55, now() - interval '3 days'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'algebra', 0.48, now() - interval '3 hours'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'chemistry', 0.42, now() - interval '5 days'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'multiplication', 0.71, now() - interval '6 days')
on conflict (child_id, topic) do update set
  score = excluded.score,
  updated_at = excluded.updated_at;

-- Mastery for Sam
insert into public.mastery_scores (child_id, topic, score, updated_at) values
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2', 'multiplication', 0.58, now() - interval '1 day'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2', 'addition', 0.82, now() - interval '3 days'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2', 'subtraction', 0.45, now() - interval '4 days')
on conflict (child_id, topic) do update set
  score = excluded.score,
  updated_at = excluded.updated_at;

insert into public.mastery_events (child_id, session_id, event, topic, score) values
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
   'dddddddd-dddd-dddd-dddd-ddddddddddd1', 'check_ok', 'fractions', 0.78),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
   'dddddddd-dddd-dddd-dddd-ddddddddddd2', 'mistake_caught', 'decimals', 0.64),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
   'dddddddd-dddd-dddd-dddd-ddddddddddd3', 'check_ok', 'area', 0.55),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
   'dddddddd-dddd-dddd-dddd-ddddddddddd4', 'teachback_ok', 'fractions', 0.74),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
   'dddddddd-dddd-dddd-dddd-ddddddddddd5', 'check_ok', 'chemistry', 0.42),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
   'dddddddd-dddd-dddd-dddd-ddddddddddd6', 'check_ok', 'algebra', 0.48),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
   'dddddddd-dddd-dddd-dddd-dddddddddde1', 'check_ok', 'multiplication', 0.58),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
   'dddddddd-dddd-dddd-dddd-dddddddddde2', 'mistake_caught', 'addition', 0.82);
