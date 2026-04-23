'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseAApi } from '@/lib/revenue-ceiling-phase-a-api';
import { Mail, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

export default function SequenceCenterDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const seqQ = useQuery({
    queryKey: ['rc-sequences', brandId],
    queryFn: () => revenueCeilingPhaseAApi.messageSequences(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const genSeq = useMutation({
    mutationFn: () => revenueCeilingPhaseAApi.generateSequences(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-sequences', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Mail className="text-emerald-400" size={28} />
          Email / SMS Sequence Center
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Welcome, nurture, objection-handling, conversion, upsell, reactivation, and sponsor-safe sequences —
          generated per brand with email, SMS, and hybrid channel support.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Sequences"
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
        >
          {(brands ?? []).map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selected && <p className="text-sm text-gray-500 mt-2">{selected.name}</p>}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          disabled={!brandId || genSeq.isPending}
          onClick={() => genSeq.mutate()}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw size={16} className={genSeq.isPending ? 'animate-spin' : ''} />
          Generate sequences
        </button>
      </div>
      {genSeq.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(genSeq.error)}</div>
      )}

      {(seqQ.data ?? []).map((s) => (
        <div key={s.id} className="card border border-gray-800">
          <div className="flex flex-wrap items-center gap-2">
            <span className="badge-yellow text-[10px]">{s.sequence_type}</span>
            <span className="text-gray-500 text-xs">{s.channel}</span>
            {s.sponsor_safe && <span className="text-amber-400 text-xs">sponsor-safe</span>}
          </div>
          <p className="text-white font-medium mt-1">{s.title}</p>
          <ul className="mt-3 space-y-2 text-sm text-gray-400">
            {s.steps.map((st) => (
              <li key={st.id} className="border-l-2 border-emerald-900/50 pl-3">
                <span className="text-gray-500 text-xs">
                  {st.channel} · +{st.delay_hours_after_previous}h
                </span>
                <p className="text-gray-200">{st.subject_or_title}</p>
                <p className="text-xs text-gray-500 line-clamp-2">{st.body_template}</p>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {!seqQ.isLoading && !(seqQ.data ?? []).length && (
        <p className="text-gray-500">No sequences — generate.</p>
      )}
    </div>
  );
}
