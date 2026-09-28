#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import html
from html.parser import HTMLParser
import mimetypes
import os
import sqlite3
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Data folder (contains data/ and mirror/). The dashboard passes it via EXILESDB_ROOT;
# run standalone, it defaults to the folder next to this script.
_here = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ROOT = Path(os.environ.get('EXILESDB_ROOT') or _here).resolve()
MIRROR_DB = ROOT / 'data' / 'mirror.sqlite'
OFFLINE_DB = ROOT / 'data' / 'offline_site.sqlite'
MIRROR = ROOT / 'mirror'
DB_ORIGIN = 'https://db.exil.es'
ASSET_ORIGIN = 'https://i.exil.es'
LOCAL_ASSET_PREFIX = '/__asset__/i.exil.es/'
TARGETED_SOURCE = 'targeted-recovery-v1'

KNOWN_TYPES = {
    'item','spell','quest','npc','pets','pet','dungeon','area','class',
    'achievement','achievements','currency','title','worldforged',
    'gameobject','skill','map','tree','faction'
}
LISTING_PATHS = {
    '/items','/spells','/quests','/npcs','/pets','/dungeons','/areas',
    '/classes','/achievements','/currencies','/titles','/worldforged','/changes'
}

class TitleGrabber(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.in_h1 = False
        self.title = []
        self.h1 = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'title': self.in_title = True
        elif tag.lower() == 'h1': self.in_h1 = True
    def handle_endtag(self, tag):
        if tag.lower() == 'title': self.in_title = False
        elif tag.lower() == 'h1': self.in_h1 = False
    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        if self.in_h1: self.h1.append(data)
    def result(self):
        h1 = ' '.join(' '.join(self.h1).split()).strip()
        if h1: return h1
        title = ' '.join(' '.join(self.title).split()).strip()
        for prefix in ('coa-db — ', 'coa-db - '):
            if title.startswith(prefix): title = title[len(prefix):]
        return title

def ensure_layout():
    if not MIRROR_DB.exists():
        print(r'ERROR: data\mirror.sqlite was not found.')
        print('Put these files in the SAME folder as FAST_MIRROR.bat.')
        sys.exit(1)
    if not (MIRROR / 'db.exil.es').exists():
        print(r'ERROR: mirror\db.exil.es was not found.')
        sys.exit(1)

def mconn_ro():
    uri = MIRROR_DB.resolve().as_uri() + '?mode=ro'
    c = sqlite3.connect(uri, uri=True, timeout=60)
    c.row_factory = sqlite3.Row
    return c

def oconn():
    c = sqlite3.connect(OFFLINE_DB, timeout=60)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA synchronous=NORMAL')
    return c

def canonical_query(q):
    pairs = urllib.parse.parse_qsl(q, keep_blank_values=True)
    pairs.sort(key=lambda x: (x[0], x[1]))
    return urllib.parse.urlencode(pairs, doseq=True)

def route_key_parts(path, query):
    path = path or '/'
    cq = canonical_query(query)
    return path + ('?' + cq if cq else '')

def route_key(url):
    p = urllib.parse.urlparse(url)
    return route_key_parts(p.path or '/', p.query)

def type_key(url):
    p = urllib.parse.urlparse(url)
    parts = [x for x in p.path.split('/') if x]
    if not parts: return 'home', ''
    first = parts[0]
    if len(parts) >= 2 and first in KNOWN_TYPES:
        return first, '/'.join(parts[1:])
    if p.path in LISTING_PATHS:
        return 'listing', p.path.lstrip('/')
    if first in KNOWN_TYPES:
        return first, p.query or first
    return 'page', p.path.lstrip('/') or 'home'

def extract_name(local_path, url):
    if not local_path: return None
    p = ROOT / local_path
    try:
        with p.open('rb') as f:
            raw = f.read(512000)
    except Exception:
        return None
    low = raw[:12000].lower()
    if b'<html' not in low and b'<!doctype html' not in low:
        return None
    parser = TitleGrabber()
    try: parser.feed(raw.decode('utf-8', errors='replace'))
    except Exception: pass
    name = parser.result()
    if not name:
        typ, key = type_key(url)
        name = key or typ
    return ' '.join(name.split()).strip()

def final_audit():
    ensure_layout()
    c = mconn_ro()
    print('============================================================')
    print('ExilesDB Final Audit')
    print('============================================================\n')
    sp = c.execute("SELECT COUNT(*) FROM saved WHERE kind='page' AND status=200").fetchone()[0]
    sa = c.execute("SELECT COUNT(*) FROM saved WHERE kind='asset' AND status=200").fetchone()[0]
    pp = c.execute("SELECT COUNT(*) FROM queue WHERE kind='page' AND state='pending'").fetchone()[0]
    pa = c.execute("SELECT COUNT(*) FROM queue WHERE kind='asset' AND state='pending'").fetchone()[0]
    fp = c.execute("SELECT COUNT(*) FROM queue WHERE kind='page' AND state='failed'").fetchone()[0]
    fa = c.execute("SELECT COUNT(*) FROM queue WHERE kind='asset' AND state='failed'").fetchone()[0]
    targeted = {(r['state'],r['kind']):r['n'] for r in c.execute(
        "SELECT state,kind,COUNT(*) n FROM queue WHERE source=? GROUP BY state,kind", (TARGETED_SOURCE,))}
    achd = c.execute("SELECT COUNT(*) FROM saved WHERE status=200 AND url LIKE 'https://db.exil.es/achievement/%'").fetchone()[0]
    achq = c.execute("SELECT COUNT(*) FROM saved WHERE status=200 AND url LIKE 'https://db.exil.es/achievements?%'").fetchone()[0]
    wfq = c.execute("SELECT COUNT(*) FROM saved WHERE status=200 AND url LIKE 'https://db.exil.es/worldforged?%'").fetchone()[0]
    pets = c.execute("SELECT COUNT(*) FROM saved WHERE status=200 AND url LIKE 'https://db.exil.es/pets/%'").fetchone()[0]
    titles = c.execute("SELECT COUNT(*) FROM saved WHERE status=200 AND url='https://db.exil.es/titles'").fetchone()[0]
    print(f'Successful pages       : {sp:,}')
    print(f'Successful assets      : {sa:,}')
    print(f'Pending pages          : {pp:,}')
    print(f'Pending assets         : {pa:,}')
    print(f'Failed pages (all-time): {fp:,}')
    print(f'Failed assets(all-time): {fa:,}\n')
    print('Targeted recovery:')
    print(f"  pending pages : {targeted.get(('pending','page'),0):,}")
    print(f"  failed pages  : {targeted.get(('failed','page'),0):,}")
    print(f"  done pages    : {targeted.get(('done','page'),0):,}\n")
    print('Special coverage:')
    print(f'  achievement detail : {achd:,}')
    print(f'  achievement queries: {achq:,}')
    print(f'  worldforged queries: {wfq:,}')
    print(f'  pet family pages    : {pets:,}')
    print(f"  titles root present : {'YES' if titles else 'NO'}\n")
    print('Checking successful saved files exist on disk...')
    missing = []
    checked = 0
    for r in c.execute("SELECT url,local_path FROM saved WHERE status=200 AND local_path IS NOT NULL"):
        checked += 1
        if not (ROOT / r['local_path']).exists():
            missing.append((r['url'], r['local_path']))
            if len(missing) >= 100: break
    print(f'Files checked          : {checked:,}')
    print(f'Missing files found    : {len(missing):,}\n')
    c.close()
    if missing:
        print('FINAL AUDIT: FAILED - saved files are missing from disk.')
        return 2
    if targeted.get(('pending','page'),0) or targeted.get(('failed','page'),0):
        print('FINAL AUDIT: TARGETED RECOVERY NOT CLEAN.')
        return 3
    print('FINAL AUDIT: PASS')
    print('Historical 404 URLs remain recorded because the live server returned 404.')
    return 0

def schema(c):
    c.executescript('''
    DROP TABLE IF EXISTS meta; DROP TABLE IF EXISTS route; DROP TABLE IF EXISTS asset; DROP TABLE IF EXISTS search_index;
    CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE route(route_key TEXT PRIMARY KEY,url TEXT NOT NULL,local_path TEXT NOT NULL,content_type TEXT,bytes INTEGER,page_type TEXT,page_key TEXT);
    CREATE TABLE asset(asset_key TEXT PRIMARY KEY,url TEXT NOT NULL,local_path TEXT NOT NULL,content_type TEXT,bytes INTEGER);
    CREATE TABLE search_index(id INTEGER PRIMARY KEY,name TEXT NOT NULL,name_lower TEXT NOT NULL,page_type TEXT,page_key TEXT,url TEXT NOT NULL,route_key TEXT NOT NULL);
    CREATE INDEX idx_search_name ON search_index(name_lower);
    CREATE INDEX idx_search_key ON search_index(page_key);
    CREATE INDEX idx_search_type ON search_index(page_type);
    ''')

def build():
    ensure_layout()
    mc = mconn_ro(); oc = oconn(); schema(oc)
    pages = list(mc.execute("SELECT url,local_path,content_type,bytes FROM saved WHERE kind='page' AND status=200 AND local_path IS NOT NULL"))
    assets = list(mc.execute("SELECT url,local_path,content_type,bytes FROM saved WHERE kind='asset' AND status=200 AND local_path IS NOT NULL"))
    print('============================================================')
    print('ExilesDB Offline Site Builder')
    print('============================================================')
    print('This does NOT copy the 13+ GB mirror.\n')
    print(f'Indexing {len(pages):,} page routes...')
    batch=[]
    for i,r in enumerate(pages,1):
        typ,key=type_key(r['url'])
        batch.append((route_key(r['url']),r['url'],r['local_path'],r['content_type'] or '',int(r['bytes'] or 0),typ,key))
        if len(batch)>=5000:
            oc.executemany('INSERT OR REPLACE INTO route VALUES(?,?,?,?,?,?,?)',batch); oc.commit(); batch=[]
        if i%50000==0: print(f'  routes {i:,}/{len(pages):,}')
    if batch: oc.executemany('INSERT OR REPLACE INTO route VALUES(?,?,?,?,?,?,?)',batch); oc.commit()
    print(f'Indexing {len(assets):,} assets...')
    batch=[]
    for r in assets:
        p=urllib.parse.urlparse(r['url'])
        batch.append((route_key_parts(p.path or '/',p.query),r['url'],r['local_path'],r['content_type'] or '',int(r['bytes'] or 0)))
        if len(batch)>=5000:
            oc.executemany('INSERT OR REPLACE INTO asset VALUES(?,?,?,?,?)',batch); oc.commit(); batch=[]
    if batch: oc.executemany('INSERT OR REPLACE INTO asset VALUES(?,?,?,?,?)',batch); oc.commit()
    print('\nBuilding local search index (one-time scan)...')
    def work(r):
        p=urllib.parse.urlparse(r['url'])
        if p.path in LISTING_PATHS: return None
        name=extract_name(r['local_path'],r['url'])
        if not name: return None
        typ,key=type_key(r['url'])
        return (name,name.lower(),typ,key,r['url'],route_key(r['url']))
    total=len(pages); inserted=0; chunk=2000
    workers=min(16,max(4,(os.cpu_count() or 8)*2))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0,total,chunk):
            part=pages[start:start+chunk]
            rows=[x for x in pool.map(work,part) if x]
            if rows:
                oc.executemany('INSERT INTO search_index(name,name_lower,page_type,page_key,url,route_key) VALUES(?,?,?,?,?,?)',rows)
                oc.commit(); inserted+=len(rows)
            done=min(start+chunk,total)
            if done%20000==0 or done==total: print(f'  scanned {done:,}/{total:,} | searchable {inserted:,}')
    for k,v in [('built_at',str(time.time())),('route_count',str(len(pages))),('asset_count',str(len(assets))),('search_count',str(inserted))]:
        oc.execute('INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)',(k,v))
    oc.commit(); oc.execute('VACUUM'); oc.close(); mc.close()
    print('\nBUILD COMPLETE')
    print(f'Routes      : {len(pages):,}')
    print(f'Assets      : {len(assets):,}')
    print(f'Search rows : {inserted:,}')
    print('Next: START_EXILES_DB.bat')
    return 0

def rewrite_html(text):
    return text.replace(ASSET_ORIGIN+'/',LOCAL_ASSET_PREFIX).replace(DB_ORIGIN,'')

def shell(title,body):
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>html,body{{background:#0c0d10;color:#d6d3c9;font-family:system-ui;margin:0}}main{{max-width:1100px;margin:48px auto;padding:0 24px}}a{{color:#d9b46b}}input{{background:#151719;color:#eee;border:1px solid #444;padding:10px;width:min(650px,80vw)}}button{{padding:10px 14px}}.row{{padding:10px 0;border-bottom:1px solid #24272b}}.muted{{color:#8e918f}}.badge{{font-size:12px;border:1px solid #555;padding:2px 6px;margin-right:8px;border-radius:4px}}</style></head><body><main>{body}</main></body></html>'''.encode('utf-8')

class Handler(BaseHTTPRequestHandler):
    server_version='ExilesDBOffline/1.0'
    def log_message(self,fmt,*args):
        if args and str(args[1]).startswith(('4','5')): super().log_message(fmt,*args)
    def db(self):
        c=sqlite3.connect(OFFLINE_DB,timeout=10); c.row_factory=sqlite3.Row; return c
    def sendb(self,data,ctype,status=200):
        self.send_response(status); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(data))); self.end_headers()
        if self.command!='HEAD': self.wfile.write(data)
    def do_HEAD(self): self.do_GET()
    def do_GET(self):
        p=urllib.parse.urlparse(self.path); path=p.path or '/'
        if path=='/search': return self.search(p.query)
        if path=='/__offline_status__': return self.status()
        if path=='/__exilesdb_root__': return self.sendb(str(ROOT).encode('utf-8'),'text/plain; charset=utf-8')
        if path.startswith(LOCAL_ASSET_PREFIX): return self.asset(path,p.query)
        return self.page(path,p.query)
    def page(self,path,query):
        c=self.db(); rk=route_key_parts(path,query); row=c.execute('SELECT * FROM route WHERE route_key=?',(rk,)).fetchone(); fallback=False
        if row is None and path in LISTING_PATHS:
            row=c.execute('SELECT * FROM route WHERE route_key=?',(path,)).fetchone(); fallback=row is not None
        c.close()
        if row is None:
            return self.sendb(shell('Not archived',f'<h1>Offline page not archived</h1><p><code>{html.escape(self.path)}</code></p><p><a href="/">Home</a> · <a href="/search">Search</a></p>'),'text/html; charset=utf-8',404)
        fp=ROOT/row['local_path']
        if not fp.exists(): return self.sendb(shell('Missing file','<h1>Archived file missing</h1>'),'text/html; charset=utf-8',500)
        data=fp.read_bytes(); ctype=row['content_type'] or mimetypes.guess_type(fp.name)[0] or 'application/octet-stream'
        if 'html' in ctype.lower() or fp.suffix.lower() in ('.html','.htm'):
            text=rewrite_html(data.decode('utf-8',errors='replace'))
            if fallback:
                note='<div style="position:fixed;bottom:8px;right:8px;z-index:99999;background:#111;border:1px solid #555;padding:6px 9px;color:#bbb">Offline snapshot: this filter was not archived; showing base listing.</div>'
                text=text.replace('</body>',note+'</body>')
            data=text.encode('utf-8'); ctype='text/html; charset=utf-8'
        return self.sendb(data,ctype)
    def asset(self,path,query):
        original='/'+path[len(LOCAL_ASSET_PREFIX):]; c=self.db(); keys=[route_key_parts(original,query),route_key_parts(original,'')]
        row=None
        for k in keys:
            row=c.execute('SELECT * FROM asset WHERE asset_key=?',(k,)).fetchone()
            if row: break
        if row is None:
            row=c.execute('SELECT * FROM asset WHERE asset_key LIKE ? ORDER BY LENGTH(asset_key) LIMIT 1',(original+'%',)).fetchone()
        c.close()
        if row is None: return self.send_error(404,'Asset not archived')
        fp=ROOT/row['local_path']
        if not fp.exists(): return self.send_error(404,'Archived asset missing')
        ctype=row['content_type'] or mimetypes.guess_type(fp.name)[0] or 'application/octet-stream'
        return self.sendb(fp.read_bytes(),ctype)
    def search(self,query):
        q=urllib.parse.parse_qs(query).get('q',[''])[0].strip(); form=f'<form><input name="q" value="{html.escape(q)}" placeholder="Search items, spells, quests, NPCs…"><button>Search</button></form>'
        if not q: return self.sendb(shell('Local Search','<p><a href="/">← Home</a></p><h1>Local ExilesDB Search</h1>'+form),'text/html; charset=utf-8')
        c=self.db(); ql=q.lower(); contains='%'+ql+'%'; prefix=ql+'%'
        if q.isdigit(): rows=c.execute('SELECT * FROM search_index WHERE page_key=? OR name_lower LIKE ? ORDER BY CASE WHEN page_key=? THEN 0 ELSE 1 END,LENGTH(name) LIMIT 150',(q,contains,q)).fetchall()
        else: rows=c.execute('SELECT * FROM search_index WHERE name_lower LIKE ? ORDER BY CASE WHEN name_lower LIKE ? THEN 0 ELSE 1 END,LENGTH(name),name LIMIT 150',(contains,prefix)).fetchall()
        c.close(); result=[]
        for r in rows: result.append(f'<div class="row"><span class="badge">{html.escape(r["page_type"] or "page")}</span><a href="{html.escape(r["route_key"])}">{html.escape(r["name"])}</a> <span class="muted">{html.escape(r["page_key"] or "")}</span></div>')
        body='<p><a href="/">← Home</a></p><h1>Local ExilesDB Search</h1>'+form+f'<p class="muted">{len(rows)} result(s)</p>'+(''.join(result) if result else '<p>No local matches.</p>')
        return self.sendb(shell('Local Search',body),'text/html; charset=utf-8')
    def status(self):
        c=self.db(); meta={r['key']:r['value'] for r in c.execute('SELECT key,value FROM meta')}; c.close()
        body='<p><a href="/">← Home</a></p><h1>Offline Archive Status</h1>'+''.join(f'<p>{html.escape(k)}: <b>{html.escape(v)}</b></p>' for k,v in sorted(meta.items()))
        return self.sendb(shell('Offline Status',body),'text/html; charset=utf-8')

def serve(port,open_browser):
    ensure_layout()
    if not OFFLINE_DB.exists():
        print('ERROR: data\\offline_site.sqlite does not exist. Run BUILD_OFFLINE_SITE.bat first.'); sys.exit(1)
    srv=ThreadingHTTPServer(('127.0.0.1',port),Handler); url=f'http://127.0.0.1:{port}/'
    print('============================================================'); print('ExilesDB OFFLINE'); print('============================================================'); print(f'Local site: {url}'); print('Press Ctrl+C to stop.\n')
    if open_browser: threading.Timer(1.0,lambda:webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print('\nStopping local ExilesDB...')
    finally: srv.server_close()

def main():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True); s.add_parser('audit'); s.add_parser('build'); sp=s.add_parser('serve'); sp.add_argument('--port',type=int,default=8080); sp.add_argument('--open',action='store_true'); a=p.parse_args()
    if a.cmd=='audit': raise SystemExit(final_audit())
    if a.cmd=='build': raise SystemExit(build())
    if a.cmd=='serve': serve(a.port,a.open)
if __name__=='__main__': main()
