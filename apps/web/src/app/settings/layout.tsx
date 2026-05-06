import Link from 'next/link';

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside className="w-48 border-r border-gray-200 p-4">
        <h1 className="font-semibold mb-3">Settings</h1>
        <nav className="space-y-1 text-sm">
          <Link href="/settings/skills" className="block px-2 py-1 rounded hover:bg-gray-100">
            Skills
          </Link>
          <Link href="/settings/mcp-servers" className="block px-2 py-1 rounded hover:bg-gray-100">
            MCP Servers
          </Link>
        </nav>
      </aside>
      <main className="flex-1">{children}</main>
    </div>
  );
}
