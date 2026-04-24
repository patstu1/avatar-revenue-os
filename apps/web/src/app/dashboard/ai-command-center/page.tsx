// Phase 0 containment: page hidden during production-trust restoration.
// Surfaced zero/synthetic data or was not operational.
// Restored after Phase 1 data purge + real data flow.
export default function Hidden() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-6">
      <div className="max-w-xl text-center">
        <div className="font-mono text-[10px] tracking-[0.25em] uppercase text-yellow-400 mb-4">
          Phase 0 · Temporarily Hidden
        </div>
        <h1 className="text-2xl font-display mb-4 text-white">
          This surface is hidden during production-trust restoration.
        </h1>
        <p className="text-sm text-white/60 leading-relaxed">
          During an audit it was found to render zero / synthetic data or
          surface disconnected endpoints. It will return after Phase&nbsp;1
          data-purge and real data flow is established.
        </p>
        <p className="mt-6 text-[10px] font-mono text-white/30 tracking-widest">
          audit: 2026-04-22 · restoration in progress
        </p>
      </div>
    </div>
  );
}
