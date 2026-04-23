'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { lec2Api } from '@/lib/live-execution-phase2-api';
import { useBrandId } from '@/hooks/useBrandId';
import { CheckCircle2, RefreshCw } from 'lucide-react';

type CapabilityRow = {
  id: string;
  profile_ready: boolean;
  credential_valid: boolean;
  platform_supported: boolean;
  blocker_summary?: string | null;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function asList<T>(data: unknown): T[] {
  return Array.isArray(data) ? (data as T[]) : [];
}

export default function BufferReadinessPage() {
  const qc = useQueryClient();
  const brandId = useBrandId();

  const { data: capsRaw, isLoading } = useQuery({
    queryKey: ['lec2-buffer-capabilities', brandId],
    queryFn: () => lec2Api.bufferCapabilities(brandId!).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recomputeMut = useMutation({
    mutationFn: () => lec2Api.recomputeBufferCapabilities(brandId!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lec2-buffer-capabilities', brandId] }),
  });

  const rows = asList<CapabilityRow>(capsRaw);

  if (!brandId) {
    return <div className="card text-center py-12 text-gray-500">No active brand selected. Use the brand switcher in the top bar.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <CheckCircle2 className="text-brand-500" size={28} aria-hidden />
            Buffer Capability / Readiness
          </h1>
          <p className="text-gray-400 mt-1">Profile, credential, and platform readiness for Buffer execution.</p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 disabled:opacity-50 shrink-0"
          disabled={!brandId || recomputeMut.isPending}
          onClick={() => recomputeMut.mutate()}
        >
          <RefreshCw size={16} className={recomputeMut.isPending ? 'animate-spin' : ''} />
          Recompute
        </button>
      </div>

      {recomputeMut.isError && (
        <div className="card border-amber-900/50 text-amber-200 text-sm">{errMessage(recomputeMut.error)}</div>
      )}
      {recomputeMut.isSuccess && (
        <div className="card border-emerald-900/50 text-emerald-300 text-sm">Recompute complete.</div>
      )}

      <div className="card">
        <p className="text-xs text-gray-500">Scoped to the active brand (use the top-bar switcher to change brand).</p>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-3">Capability checks</h2>
        {isLoading ? (
          <p className="text-gray-500">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-gray-500">No capability checks yet. Recompute to evaluate readiness.</p>
        ) : (
          <div className="overflow-x-auto border border-gray-800 rounded-lg">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-400">
                  <th className="p-3 font-medium">Profile ready</th>
                  <th className="p-3 font-medium">Credential valid</th>
                  <th className="p-3 font-medium">Platform supported</th>
                  <th className="p-3 font-medium">Blocker summary</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-gray-800/80 text-gray-300">
                    <td className="p-3 text-white">{row.profile_ready ? 'Yes' : 'No'}</td>
                    <td className="p-3">{row.credential_valid ? 'Yes' : 'No'}</td>
                    <td className="p-3">{row.platform_supported ? 'Yes' : 'No'}</td>
                    <td className="p-3 text-gray-400 max-w-md">{row.blocker_summary ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
