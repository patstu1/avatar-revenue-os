export default function DashboardLoading() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-64 bg-gray-800 rounded" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 bg-gray-800/60 rounded-xl border border-gray-800" />
        ))}
      </div>
      <div className="h-64 bg-gray-800/60 rounded-xl border border-gray-800" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[1, 2].map((i) => (
          <div key={i} className="h-48 bg-gray-800/60 rounded-xl border border-gray-800" />
        ))}
      </div>
    </div>
  );
}
