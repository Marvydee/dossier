-- Docket Prospector platform schema
-- Applied on top of Supabase's built-in auth.users / auth schema.

-- ── profiles ──────────────────────────────────────────────────────────────
create table public.profiles (
  id              uuid primary key references auth.users(id) on delete cascade,
  email           text not null,
  token_balance   int not null default 3,
  plan            text not null default 'free' check (plan in ('free', 'unlimited')),
  plan_expires_at timestamptz,
  created_at      timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = id);
-- No insert/update/delete policies for authenticated/anon: all writes happen
-- via the backend's service-role key, which bypasses RLS by design.

-- Creates a profile row (with the 3 free signup tokens) the moment a new
-- auth.users row appears — i.e. right after Supabase's own email-verification
-- signup flow completes.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);

  insert into public.token_transactions (user_id, delta, reason)
  values (new.id, 3, 'signup_bonus');

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── categories ────────────────────────────────────────────────────────────
create table public.categories (
  slug              text primary key,
  label             text not null,
  businesslist_slug text,
  finelib_slug      text,
  osm_shop_tag      text,
  osm_amenity_tag   text,
  active            boolean not null default true
);

alter table public.categories enable row level security;

create policy "categories_select_all"
  on public.categories for select
  using (true);

-- ── cities ────────────────────────────────────────────────────────────────
create table public.cities (
  slug        text primary key,
  label       text not null,
  country     text not null default 'Nigeria',
  is_nigeria  boolean not null default true,
  lat         double precision not null,
  lon         double precision not null,
  active      boolean not null default true
);

alter table public.cities enable row level security;

create policy "cities_select_all"
  on public.cities for select
  using (true);

-- ── generation_jobs ───────────────────────────────────────────────────────
create table public.generation_jobs (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users(id) on delete cascade,
  status           text not null default 'queued'
                     check (status in ('queued', 'running', 'completed', 'failed')),
  categories       text[] not null,
  cities           text[] not null,
  progress_current int not null default 0,
  progress_total   int not null default 0,
  result_path      text,
  row_count        int,
  error            text,
  tokens_spent     int not null default 1,
  created_at       timestamptz not null default now(),
  started_at       timestamptz,
  completed_at     timestamptz
);

alter table public.generation_jobs enable row level security;

create policy "jobs_select_own"
  on public.generation_jobs for select
  using (auth.uid() = user_id);
-- Writes (insert on creation, updates for status/progress) happen via the
-- backend's service-role key only.

create index generation_jobs_user_id_created_at_idx
  on public.generation_jobs (user_id, created_at desc);

-- Lets the worker atomically claim the oldest queued job without two worker
-- ticks racing to process the same row.
create index generation_jobs_queued_idx
  on public.generation_jobs (created_at)
  where status = 'queued';

-- ── token_transactions (append-only ledger) ──────────────────────────────
create table public.token_transactions (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  delta               int not null,
  reason              text not null
                        check (reason in ('signup_bonus', 'job_spend', 'job_refund',
                                           'purchase', 'unlimited_plan')),
  job_id              uuid references public.generation_jobs(id),
  paystack_reference  text,
  created_at          timestamptz not null default now()
);

alter table public.token_transactions enable row level security;

create policy "token_transactions_select_own"
  on public.token_transactions for select
  using (auth.uid() = user_id);

-- Belt-and-braces against credit_purchase() below: even if two webhook
-- deliveries for the same payment race each other in truly concurrent
-- transactions (the exists-check in credit_purchase can't see an uncommitted
-- sibling transaction), this makes the second insert fail instead of both
-- succeeding, so a duplicate credit is still structurally impossible.
create unique index token_transactions_paystack_reference_idx
  on public.token_transactions (paystack_reference)
  where paystack_reference is not null;

-- ── payments ──────────────────────────────────────────────────────────────
create table public.payments (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  paystack_reference  text not null unique,
  amount_kobo         int not null,
  plan                text not null check (plan in ('tokens_10', 'unlimited_year')),
  status              text not null default 'pending'
                        check (status in ('pending', 'success', 'failed')),
  created_at          timestamptz not null default now()
);

alter table public.payments enable row level security;

create policy "payments_select_own"
  on public.payments for select
  using (auth.uid() = user_id);

-- ── spend_token(): atomic token/unlimited-plan check-and-deduct ────────────
-- Called via Supabase RPC from the backend when a job is created. Doing the
-- balance check and the decrement inside one function (one transaction)
-- closes the race condition where two concurrent requests both read
-- token_balance > 0 before either one writes the decrement.
create function public.spend_token(p_user_id uuid, p_job_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_plan            text;
  v_plan_expires_at timestamptz;
  v_balance         int;
begin
  select plan, plan_expires_at, token_balance
    into v_plan, v_plan_expires_at, v_balance
    from public.profiles
   where id = p_user_id
   for update;

  if v_plan = 'unlimited' and v_plan_expires_at > now() then
    insert into public.token_transactions (user_id, delta, reason, job_id)
    values (p_user_id, 0, 'job_spend', p_job_id);
    return true;
  end if;

  if v_balance > 0 then
    update public.profiles set token_balance = token_balance - 1 where id = p_user_id;
    insert into public.token_transactions (user_id, delta, reason, job_id)
    values (p_user_id, -1, 'job_spend', p_job_id);
    return true;
  end if;

  return false;
end;
$$;

-- ── refund_token(): reverses a job_spend when a job fails ───────────────────
create function public.refund_token(p_user_id uuid, p_job_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_spent_delta int;
begin
  select delta into v_spent_delta
    from public.token_transactions
   where user_id = p_user_id and job_id = p_job_id and reason = 'job_spend'
   limit 1;

  if v_spent_delta = -1 then
    update public.profiles set token_balance = token_balance + 1 where id = p_user_id;
  end if;

  insert into public.token_transactions (user_id, delta, reason, job_id)
  values (p_user_id, -v_spent_delta, 'job_refund', p_job_id);
end;
$$;

-- ── credit_purchase(): applies a successful Paystack payment ────────────────
-- Idempotent on paystack_reference: a replayed webhook (Paystack retries on
-- any non-2xx response, and delivery is technically at-least-once even on
-- success) must never credit tokens or extend the plan twice. The uniqueness
-- check and the credit happen in one transaction, closing the same race
-- window spend_token() closes for spending.
create function public.credit_purchase(
  p_user_id uuid, p_plan text, p_paystack_reference text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if exists (
    select 1 from public.token_transactions
     where paystack_reference = p_paystack_reference
  ) then
    return;  -- already credited — replayed webhook, no-op
  end if;

  if p_plan = 'tokens_10' then
    update public.profiles set token_balance = token_balance + 10 where id = p_user_id;
    insert into public.token_transactions (user_id, delta, reason, paystack_reference)
    values (p_user_id, 10, 'purchase', p_paystack_reference);

  elsif p_plan = 'unlimited_year' then
    update public.profiles
       set plan = 'unlimited',
           plan_expires_at = greatest(coalesce(plan_expires_at, now()), now()) + interval '365 days'
     where id = p_user_id;
    insert into public.token_transactions (user_id, delta, reason, paystack_reference)
    values (p_user_id, 0, 'unlimited_plan', p_paystack_reference);
  end if;
exception
  when unique_violation then
    return;  -- a concurrent call already credited this exact reference — no-op
end;
$$;

-- ── claim_next_job(): atomic queue claim ─────────────────────────────────
-- Standard SKIP LOCKED pattern: even though MVP runs a single in-process
-- worker loop, this makes it safe to later run multiple worker instances
-- without two of them ever picking up the same job.
create function public.claim_next_job()
returns setof public.generation_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
  v_job_id uuid;
begin
  select id into v_job_id
    from public.generation_jobs
   where status = 'queued'
   order by created_at
   for update skip locked
   limit 1;

  if v_job_id is null then
    return;
  end if;

  return query
    update public.generation_jobs
       set status = 'running', started_at = now()
     where id = v_job_id
    returning *;
end;
$$;
