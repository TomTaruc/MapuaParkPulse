#!/usr/bin/env python3
"""Mapúa ParkPulse role-scoped demonstration server for Replit.

Demo identities are NOT university accounts. Never store real credentials or real
student data. For class demonstration only, not a production authentication system.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
STATE_FILE=ROOT/'parkpulse_live_state.json'
ACCOUNTS_FILE=ROOT/'parkpulse_demo_accounts.json'
LOCK=threading.RLock()
SESSIONS={}
LOGIN_FAILURES={}
ROUNDS=175_000

def now_ms(): return int(time.time()*1000)

def initial():
    t=now_ms()
    initial_slots={1,2,3,4,5,6,7,8,9,10,13,14,15,16,19,20,21,22,27,28}
    ids=[f'S-{i:02}' for i in range(1,35)]
    return {
        'version':4,'capacity':34,'registryApproved':False,'threshold':80,
        'staleMinutes':60,'queueStaleMinutes':45,
        'bay':{k:('occupied' if int(k[2:]) in initial_slots else 'available') for k in ids},
        'initialOccupied':[k for k in ids if int(k[2:]) in initial_slots],
        'facility':'OPEN','queue':'MODERATE','queueAt':t-5*60000,'notice':'',
        'lastBayAt':t-2*60000,'lastVerifiedAt':t-30*60000,'shift':True,
        'flags':[],'log':[{'id':'DEMO-INIT','time':t-30*60000,'type':'OPENING',
          'space':'—','before':'—','after':'20 occupied','actor':'Demo Admin',
          'note':'Opening demonstration inventory','countAfter':20}],
        'pilot':{'accuracy':None,'timeliness':None,'correction':None,'queue':None,'usability':None,'waiting':None},
        'queueHistory':[],'revision':'B','notes':''}

def validate_state(s):
    if not isinstance(s,dict) or s.get('version')!=4: return False
    cap=s.get('capacity'); bay=s.get('bay')
    return (type(cap)==int and 1<=cap<=34 and isinstance(bay,dict)
            and all(bay.get(f'S-{i:02}') in ('occupied','available') for i in range(1,35))
            and isinstance(s.get('log'),list) and isinstance(s.get('flags'),list))

def read_state():
    try:
        doc=json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if validate_state(doc.get('state')) and type(doc.get('revision'))==int:
            return doc
    except (OSError,ValueError,TypeError): pass
    return {'revision':1,'state':initial(),'requests':{}}

def atomically_write(path,value):
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)

def password_hash(password):
    salt=secrets.token_bytes(16)
    hashed=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,ROUNDS)
    return salt.hex()+':'+hashed.hex()

def check_password(password,stored):
    try:
        salt_hex,hash_hex=stored.split(':')
        actual=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),bytes.fromhex(salt_hex),ROUNDS)
        return hmac.compare_digest(actual,bytes.fromhex(hash_hex))
    except (ValueError,AttributeError): return False

def sample_account(username,name,role,password):
    return {'id':str(uuid.uuid4()),'username':username,'name':name,'role':role,
      'passwordHash':password_hash(password),'active':True,'createdAt':now_ms(),'updatedAt':now_ms()}

def read_accounts():
    try:
        doc=json.loads(ACCOUNTS_FILE.read_text(encoding='utf-8'))
        if isinstance(doc.get('users'),list) and any(a.get('role')=='admin' for a in doc['users']):
            return doc
    except (OSError,ValueError,TypeError): pass
    return {'users':[
      sample_account('admin.demo','Demo Admin','admin','DemoAdmin#26'),
      sample_account('guard.demo','Demo Guard','guard','DemoGuard#26'),
      sample_account('202600001','Demo Student','student','DemoStudent#26')
    ]}

DOC=read_state()
ACCOUNTS=read_accounts()
if not ACCOUNTS_FILE.exists(): atomically_write(ACCOUNTS_FILE,ACCOUNTS)

def save_state(): atomically_write(STATE_FILE,DOC)
def save_accounts(): atomically_write(ACCOUNTS_FILE,ACCOUNTS)
def visible(a): return {k:a[k] for k in ('id','username','name','role','active','createdAt','updatedAt')}
def user_by_id(uid): return next((a for a in ACCOUNTS['users'] if a['id']==uid),None)
def user_by_username(u): return next((a for a in ACCOUNTS['users'] if a['username'].lower()==u.lower()),None)
def snap(user):
    s=DOC['state']
    if user['role']=='student':
        keys=('version','capacity','registryApproved','threshold','staleMinutes','queueStaleMinutes','bay','facility','queue','queueAt','notice','lastBayAt','lastVerifiedAt')
        s={k:s[k] for k in keys if k in s}
    return {'revision':DOC['revision'],'state':s}

def guard_write_allowed(old,new):
    allowed={'queue','queueAt','queueHistory','shift','flags','log'}
    changed={key for key in set(old)|set(new) if old.get(key)!=new.get(key)}
    if not changed.issubset(allowed): return False
    if 'flags' in changed:
        prev=old['flags'];cur=new['flags']
        if len(cur)!=len(prev)+1 or cur[1:]!=prev or cur[0].get('status')!='OPEN':return False
    if 'log' in changed:
        prev=old['log'];cur=new['log']
        if not isinstance(cur,list) or len(cur)<len(prev):return False
        if cur[len(cur)-len(prev):]!=prev:return False
        if any(e.get('type') not in ('CONGESTION','DISCREPANCY_OPEN','SHIFT') for e in cur[:len(cur)-len(prev)]):return False
    return True

class Handler(BaseHTTPRequestHandler):
    server_version='ParkPulseDemo/6.1'
    def log_message(self,fmt,*args):
        if not self.path.startswith('/api/state'):super().log_message(fmt,*args)
    def respond(self,status,body):
        raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store, max-age=0')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers();self.wfile.write(raw)
    def json_body(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<=0 or length>2_500_000:return None
            body=json.loads(self.rfile.read(length).decode('utf-8'))
            return body if isinstance(body,dict) else None
        except (ValueError,UnicodeDecodeError):return None
    def auth(self):
        h=self.headers.get('Authorization','')
        if not h.startswith('Bearer '):return None
        token=h[7:].strip()
        uid=SESSIONS.get(token)
        a=user_by_id(uid)
        return a if a and a.get('active') else None
    def authorized(self,roles):
        a=self.auth()
        if not a:return None
        return a if a['role'] in roles else None
    def do_GET(self):
        path=urlsplit(self.path).path
        if path in ('/', '/portal', '/portal.html'):
            raw=(ROOT/'portal.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw);return
        if path in ('/flowboard', '/FlowBoard.html'):
            raw=(ROOT/'FlowBoard.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw);return
        if path in ('/StageBoard.html', '/board', '/legacy-board'):
            raw=(ROOT/'StageBoard.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw);return
        if path=='/api/health':return self.respond(200,{'status':'ok','mode':'role-scoped-cloud-demo'})
        if path in ('/student','/guard','/admin','/index.html'):
            raw=(ROOT/'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw);return
        if path=='/api/auth/me':
            a=self.auth()
            return self.respond(200,{'user':visible(a)} if a else {'user':None})
        if path=='/api/state':
            a=self.auth()
            if not a:return self.respond(401,{'error':'Sign in required'})
            with LOCK:return self.respond(200,snap(a))
        if path=='/api/guards':
            a=self.authorized(('admin',))
            if not a:return self.respond(403,{'error':'Administrator access required'})
            with LOCK:
                return self.respond(200,{'guards':[visible(g) for g in ACCOUNTS['users'] if g['role']=='guard']})
        return self.respond(404,{'error':'Not found'})
    def do_POST(self):
        path=urlsplit(self.path).path
        body=self.json_body()
        if body is None:return self.respond(400,{'error':'Invalid JSON body'})
        with LOCK:
            if path=='/api/auth/login':
                user=str(body.get('username','')).strip();pw=str(body.get('password',''))
                requested=body.get('portal')
                view=body.get('roleView')
                if requested not in ('student','staff'):return self.respond(400,{'error':'Invalid sign-in portal'})
                if view not in (None,'student','guard','admin'):return self.respond(400,{'error':'Invalid role view'})
                if view=='student' and requested!='student' or view in ('guard','admin') and requested!='staff':
                    return self.respond(400,{'error':'Role view and sign-in portal disagree'})
                key=(self.client_address[0],user.lower())
                failures=LOGIN_FAILURES.get(key,[]);failures=[t for t in failures if time.time()-t<90]
                if len(failures)>=8:return self.respond(429,{'error':'Too many attempts. Try later.'})
                a=user_by_username(user)
                valid=a is not None and a.get('active') and ((requested=='student' and a['role']=='student') or (requested=='staff' and a['role'] in ('guard','admin'))) and (not view or a['role']==view) and check_password(pw,a['passwordHash'])
                if not valid:
                    failures.append(time.time());LOGIN_FAILURES[key]=failures
                    return self.respond(401,{'error':'Invalid username or password'})
                LOGIN_FAILURES.pop(key,None)
                token=secrets.token_urlsafe(32);SESSIONS[token]=a['id']
                return self.respond(200,{'token':token,'user':visible(a)})
            if path=='/api/auth/logout':
                h=self.headers.get('Authorization','')
                if h.startswith('Bearer '):SESSIONS.pop(h[7:].strip(),None)
                return self.respond(200,{'ok':True})
            a=self.auth()
            if not a:return self.respond(401,{'error':'Sign in required'})
            if path=='/api/guards':
                if a['role']!='admin':return self.respond(403,{'error':'Administrator access required'})
                uname=str(body.get('username','')).strip();name=str(body.get('name','')).strip();pw=str(body.get('password',''))
                if not 3<=len(uname)<=32 or not all(x.isalnum() or x in '._-' for x in uname):return self.respond(400,{'error':'Username must use 3–32 letters, numbers, dots, underscores or hyphens'})
                if not 2<=len(name)<=70 or len(pw)<10 or len(pw)>120:return self.respond(400,{'error':'Enter a name and a temporary password of at least 10 characters'})
                if user_by_username(uname):return self.respond(409,{'error':'Username already exists'})
                guard=sample_account(uname,name,'guard',pw)
                ACCOUNTS['users'].append(guard);save_accounts()
                return self.respond(201,{'guard':visible(guard)})
            if path=='/api/reset':
                if a['role']!='admin':return self.respond(403,{'error':'Admin required'})
                if body.get('confirm')!='RESET_DEMO':return self.respond(400,{'error':'Confirmation required'})
                DOC['state']=initial();DOC['revision']+=1;DOC['requests']={};save_state()
                return self.respond(200,{**snap(a),'changed':True})
            if path=='/api/bay':
                if a['role']!='guard':return self.respond(403,{'error':'Guard access required'})
                request=body.get('requestId')
                if not isinstance(request,str) or not 4<=len(request)<=100:return self.respond(400,{'error':'Missing transaction ID'})
                if request in DOC['requests']:return self.respond(200,{**snap(a),'changed':False,'duplicateRequest':True})
                id=body.get('space');status=body.get('status');s=DOC['state'];cap=s['capacity']
                if id not in [f'S-{i:02}' for i in range(1,cap+1)]:return self.respond(400,{'error':'Inactive space'})
                if status not in ('occupied','available'):return self.respond(400,{'error':'Invalid space status'})
                before=s['bay'][id]
                if before==status:return self.respond(200,{**snap(a),'changed':False,'reason':'Already '+status})
                if s.get('facility')=='CLOSED' and status=='occupied':return self.respond(409,{**snap(a),'error':'Facility closed to new occupied reports'})
                s['bay'][id]=status;t=now_ms();s['lastBayAt']=t
                count=sum(s['bay'][f'S-{i:02}']=='occupied' for i in range(1,cap+1))
                s['log'].insert(0,{'id':'EV-'+str(uuid.uuid4())[:14],'time':t,'type':'SPACE_STATUS',
                    'space':id,'before':before,'after':status,'actor':a['name'],
                    'note':'Physical space observation','countAfter':count,'observationAt':t})
                s['log']=s['log'][:1500]
                DOC['requests'][request]=t
                if len(DOC['requests'])>3000:DOC['requests']=dict(list(DOC['requests'].items())[-1500:])
                DOC['revision']+=1;save_state()
                return self.respond(200,{**snap(a),'changed':True})
            if path=='/api/state':
                if a['role']=='student':return self.respond(403,{'error':'Student view cannot modify parking records'})
                new=body.get('state')
                if not validate_state(new):return self.respond(400,{'error':'Invalid state'})
                if body.get('revision')!=DOC['revision']:
                    return self.respond(409,{**snap(a),'error':'Another window changed the data. Latest record loaded.'})
                old=DOC['state']
                if a['role']=='guard' and not guard_write_allowed(old,new):
                    return self.respond(403,{'error':'Guard permission does not allow this administrative change'})
                deltas=[k for k in new['bay'] if new['bay'][k]!=old['bay'][k]]
                if deltas and len(new['log'])<=len(old['log']):return self.respond(400,{'error':'Space changes require audit events'})
                DOC['state']=new;DOC['revision']+=1;save_state()
                return self.respond(200,{**snap(a),'changed':True})
        return self.respond(404,{'error':'Unknown endpoint'})
    def do_PATCH(self):
        path=urlsplit(self.path).path
        if not path.startswith('/api/guards/'):
            return self.respond(404,{'error':'Not found'})
        body=self.json_body()
        if body is None:return self.respond(400,{'error':'Invalid JSON'})
        with LOCK:
            a=self.authorized(('admin',))
            if not a:return self.respond(403,{'error':'Administrator access required'})
            g=user_by_id(path[len('/api/guards/'):])
            if not g or g['role']!='guard':return self.respond(404,{'error':'Guard not found'})
            name=str(body.get('name',g['name'])).strip();uname=str(body.get('username',g['username'])).strip()
            pw=body.get('password')
            if not 2<=len(name)<=70 or not 3<=len(uname)<=32 or not all(c.isalnum() or c in '._-' for c in uname):
                return self.respond(400,{'error':'Invalid display name or username'})
            dupe=user_by_username(uname)
            if dupe and dupe['id']!=g['id']:return self.respond(409,{'error':'Username already exists'})
            if pw is not None and (not isinstance(pw,str) or not 10<=len(pw)<=120):
                return self.respond(400,{'error':'New password must have at least 10 characters'})
            if 'active' in body and type(body['active']) is not bool:
                return self.respond(400,{'error':'Active status must be true or false'})
            g['name']=name;g['username']=uname
            if 'active' in body:g['active']=body['active']
            if pw:g['passwordHash']=password_hash(pw)
            g['updatedAt']=now_ms();save_accounts()
            if pw or not g['active']:
                for token,uid in list(SESSIONS.items()):
                    if uid==g['id']:SESSIONS.pop(token,None)
            return self.respond(200,{'guard':visible(g)})
    def do_DELETE(self):
        path=urlsplit(self.path).path
        if not path.startswith('/api/guards/'):
            return self.respond(404,{'error':'Not found'})
        with LOCK:
            a=self.authorized(('admin',))
            if not a:return self.respond(403,{'error':'Administrator access required'})
            g=user_by_id(path[len('/api/guards/'):])
            if not g or g['role']!='guard':return self.respond(404,{'error':'Guard not found'})
            g['active']=False;g['updatedAt']=now_ms()
            for token,uid in list(SESSIONS.items()):
                if uid==g['id']:SESSIONS.pop(token,None)
            save_accounts()
            return self.respond(200,{'guard':visible(g),'message':'Guard deactivated; historical records preserved'})

def main():
    p=argparse.ArgumentParser(description='Mapúa ParkPulse Replit cloud demo (one HTTP port)')
    p.add_argument('--port',type=int,default=int(os.getenv('PORT','3000')))
    p.add_argument('--host',default='0.0.0.0')
    args=p.parse_args()
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'ParkPulse Replit board: http://127.0.0.1:{args.port}/',flush=True)
    print('Student: /student | Guard: /guard | Admin: /admin',flush=True)
    print('Shared state updates across all three browser views.',flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
if __name__=='__main__':main()
