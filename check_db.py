import sqlite3

c = sqlite3.connect("auth.db")
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

print(tables)

c.close()
