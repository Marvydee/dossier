'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { apiFetch, ApiError } from '@/lib/api';
import {
  MAX_CATEGORIES_PER_JOB,
  MAX_CITIES_PER_JOB,
  RESULTS_PER_JOB,
  type Category,
  type City,
} from '@/lib/types';

function Picker<T extends { slug: string; label: string }>({
  title,
  items,
  selected,
  max,
  onToggle,
}: {
  title: string;
  items: T[];
  selected: string[];
  max: number;
  onToggle: (slug: string) => void;
}) {
  const [query, setQuery] = useState('');
  const filtered = items.filter((i) => i.label.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="border border-paper-line p-5">
      <div className="flex items-baseline justify-between border-b border-paper-line pb-3">
        <h3 className="font-display text-lg font-medium text-ink">{title}</h3>
        <span className={`text-xs tabular-nums ${selected.length === max ? 'text-pine' : 'text-ink-faint'}`}>
          {selected.length} / {max}
        </span>
      </div>
      <input
        type="text"
        placeholder="Search…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="mt-3 w-full border border-paper-line bg-white/60 px-3 py-1.5 text-sm text-ink focus:border-pine focus:outline-none"
      />
      <div className="mt-3 max-h-64 space-y-0.5 overflow-y-auto pr-1">
        {filtered.map((item) => {
          const isSelected = selected.includes(item.slug);
          const disabled = !isSelected && selected.length >= max;
          return (
            <label
              key={item.slug}
              className={`flex cursor-pointer items-center gap-2 px-2 py-1.5 text-sm ${
                disabled ? 'cursor-not-allowed opacity-40' : 'hover:bg-paper-dim'
              } ${isSelected ? 'text-ink' : 'text-ink-soft'}`}
            >
              <input
                type="checkbox"
                checked={isSelected}
                disabled={disabled}
                onChange={() => onToggle(item.slug)}
                className="accent-pine"
              />
              {item.label}
            </label>
          );
        })}
      </div>
    </div>
  );
}

export default function Generate() {
  const router = useRouter();
  const [categories, setCategories] = useState<Category[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedCities, setSelectedCities] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase
      .from('categories')
      .select('slug, label')
      .eq('active', true)
      .order('label')
      .then(({ data }) => setCategories(data ?? []));
    supabase
      .from('cities')
      .select('slug, label, country, is_nigeria')
      .eq('active', true)
      .order('is_nigeria', { ascending: false })
      .order('label')
      .then(({ data }) => setCities(data ?? []));
  }, []);

  const includesInternational = useMemo(
    () => selectedCities.some((slug) => cities.find((c) => c.slug === slug)?.is_nigeria === false),
    [selectedCities, cities]
  );

  function toggle(list: string[], setList: (v: string[]) => void, max: number, slug: string) {
    if (list.includes(slug)) {
      setList(list.filter((s) => s !== slug));
    } else if (list.length < max) {
      setList([...list, slug]);
    }
  }

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      const job = await apiFetch<{ id: string }>('/jobs', {
        method: 'POST',
        body: JSON.stringify({ categories: selectedCategories, cities: selectedCities }),
      });
      router.push(`/jobs/${job.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');
      setSubmitting(false);
    }
  }

  const canSubmit = selectedCategories.length > 0 && selectedCities.length > 0 && !submitting;

  return (
    <div>
      <h1 className="font-display text-3xl font-medium text-ink">Name what you need</h1>
      <p className="mt-2 max-w-2xl text-sm text-ink-soft">
        Pick up to {MAX_CATEGORIES_PER_JOB} categories and {MAX_CITIES_PER_JOB} cities.
        You&apos;ll get {RESULTS_PER_JOB} businesses total, split evenly across your selected
        cities and drawn fresh at random — each one reachable by phone or email. Costs 1 token.
      </p>

      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        <Picker
          title="Categories"
          items={categories}
          selected={selectedCategories}
          max={MAX_CATEGORIES_PER_JOB}
          onToggle={(slug) => toggle(selectedCategories, setSelectedCategories, MAX_CATEGORIES_PER_JOB, slug)}
        />
        <Picker
          title="Cities"
          items={cities}
          selected={selectedCities}
          max={MAX_CITIES_PER_JOB}
          onToggle={(slug) => toggle(selectedCities, setSelectedCities, MAX_CITIES_PER_JOB, slug)}
        />
      </div>

      {includesInternational && (
        <p className="mt-5 border-l-2 border-pine bg-pine-tint px-4 py-3 text-sm text-ink">
          Non-Nigerian cities are covered only by OpenStreetMap — expect fewer results there than
          for Nigerian cities, which also pull from two dedicated business directories.
        </p>
      )}

      {error && <p className="mt-4 text-sm text-brick">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="mt-7 rounded bg-pine px-6 py-2.5 font-medium text-paper hover:bg-pine-hover disabled:cursor-not-allowed disabled:opacity-40"
      >
        {submitting ? 'Starting…' : 'Generate (1 token)'}
      </button>
    </div>
  );
}
