# Lil-Vro parent dashboard

Next.js app for parents to review voice STEM sessions.

Demo login: `parent@thinko.local` / `password123`  
Seeded children: **Alex** (primary `CHILD_ID`) and **Sam**.

Next.js app for parents — overview, activity, mastery, and children. Designed to run
against **local Supabase** now and **hosted Supabase + Vercel** later (same code).

## Local

1. Start Supabase from the repo root (`npx supabase start && npx supabase db reset`).
2. Copy keys into `.env.local` (see `.env.local.example`).
3. `npm install && npm run dev` → http://127.0.0.1:3000  
   Demo: `parent@thinko.local` / `password123`

## Deploy on Vercel

1. Create a hosted [Supabase](https://supabase.com) project.
2. Push migrations: from repo root, `npx supabase db push` (linked to the project).
3. In Vercel, import the Git repo and set **Root Directory** to `dashboard`.
4. Add environment variables:

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://YOUR_PROJECT.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role (server only; optional for UI reads) |

5. In Supabase Auth → URL config, add your Vercel URL to redirect allow-list  
   (`https://YOUR_APP.vercel.app/**`).
6. Deploy. Create a parent account (or seed one), then add a child and put that
   `CHILD_ID` in the voice agent’s `.env` with the same project URL/service key.
