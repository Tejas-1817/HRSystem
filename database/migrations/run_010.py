"""
Migration 010 Runner: Device Inventory & Stock Management
"""
import os, sys, re, mysql.connector
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from dotenv import load_dotenv
load_dotenv()

def _split(sql):
    lines = [re.sub(r'--.*$', '', l) for l in sql.splitlines() if not l.strip().startswith('--')]
    return [s.strip() for s in '\n'.join(lines).split(';') if s.strip() and s.strip().upper() != 'USE STARTERDATA']

def run():
    with open(os.path.join(os.path.dirname(__file__), '010_inventory_management.sql')) as f:
        sql = f.read()
    conn = mysql.connector.connect(host=os.getenv('DB_HOST','localhost'), user=os.getenv('DB_USER','root'),
                                    password=os.getenv('DB_PASS',''), database=os.getenv('DB_NAME','starterdata'))
    cur = conn.cursor()
    print("🚀 Running Migration 010: Device Inventory & Stock Management ...")
    stmts, done = _split(sql), 0
    try:
        for i, s in enumerate(stmts, 1):
            try:
                cur.execute(s)
                try: cur.fetchall()
                except mysql.connector.errors.InterfaceError: pass
                done += 1
            except mysql.connector.Error as e:
                if e.errno in (1060, 1061, 1050): print(f"  ⏩ Skipped: {s[:60]}..."); done += 1
                else: raise
        conn.commit()
        print(f"✅ Migration 010 completed. ({done} statements)")
    except mysql.connector.Error as e:
        conn.rollback(); print(f"❌ Failed at stmt {i}: {e}"); sys.exit(1)
    finally:
        cur.close(); conn.close()

if __name__ == '__main__': run()
