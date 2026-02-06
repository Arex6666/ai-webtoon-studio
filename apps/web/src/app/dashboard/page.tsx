export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-2">
          Project overview coming soon
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border bg-card p-6">
          <h3 className="font-semibold">Projects</h3>
          <p className="text-2xl font-bold mt-2">0</p>
          <p className="text-sm text-muted-foreground mt-1">Total projects</p>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h3 className="font-semibold">Chapters</h3>
          <p className="text-2xl font-bold mt-2">0</p>
          <p className="text-sm text-muted-foreground mt-1">Total chapters</p>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h3 className="font-semibold">Panels</h3>
          <p className="text-2xl font-bold mt-2">0</p>
          <p className="text-sm text-muted-foreground mt-1">Total panels</p>
        </div>
      </div>
    </div>
  )
}
