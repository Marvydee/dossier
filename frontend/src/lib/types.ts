export type Category = {
  slug: string;
  label: string;
};

export type City = {
  slug: string;
  label: string;
  country: string;
  is_nigeria: boolean;
};

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

export type Job = {
  id: string;
  user_id: string;
  status: JobStatus;
  categories: string[];
  cities: string[];
  progress_current: number;
  progress_total: number;
  result_path: string | null;
  row_count: number | null;
  error: string | null;
  tokens_spent: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type Profile = {
  id: string;
  email: string;
  token_balance: number;
  plan: 'free' | 'unlimited';
  plan_expires_at: string | null;
};

export const MAX_CATEGORIES_PER_JOB = 8;
export const MAX_CITIES_PER_JOB = 8;
export const RESULTS_PER_JOB = 10;
