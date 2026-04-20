import sqlite3
conn = sqlite3.connect('webtoon_studio.db')
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)
for t in tables:
    if t == 'sqlite_sequence':
        continue
    count = c.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0]
    print(f'  {t}: {count} rows')
    if t == 'users' and count > 0:
        rows = c.execute(f"SELECT id, username, email, is_admin FROM [{t}]").fetchall()
        for row in rows:
            print(f'    -> {row}')
conn.close()
