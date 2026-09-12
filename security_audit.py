import base64,json,os,sys,uuid,requests
BASE=os.getenv('NEXUS_BASE_URL','http://127.0.0.1:8001').rstrip('/')
PASSWORD='SecurityTest123!'; TIMEOUT=20; results=[]; s=requests.Session()
def req(m,p,**kw): kw.setdefault('timeout',TIMEOUT); return s.request(m,BASE+p,**kw)
def rec(n,ok,d=''): results.append((n,ok,d)); print(f"[{'PASS' if ok else 'FAIL'}] {n}"+(f' - {d}' if d else ''))
def login():
 r=req('POST','/login',json={'email':'securitytest_77b2273c@nexusai.com','password':PASSWORD});
 try:return r.json().get('token'),r
 except:return None,r
def h(t): return {'Authorization':'Bearer '+t}
def main():
 print('='*62); print('NexusAI Backend Security Audit'); print('Target:',BASE); print('='*62)
 token,r=login(); rec('Login with valid credentials',bool(token),f'HTTP {r.status_code}')
 if not token: summary(); return 1
 r=req('GET','/documents'); rec('Missing JWT rejected',r.status_code==401,f'HTTP {r.status_code}')
 r=req('GET','/documents',headers=h('invalid.token.here')); rec('Invalid JWT rejected',r.status_code==401,f'HTTP {r.status_code}')
 parts=token.split('.')
 if len(parts)==3:
  fh=base64.urlsafe_b64encode(json.dumps({'alg':'none','typ':'JWT'},separators=(',',':')).encode()).decode().rstrip('=')
  r=req('GET','/documents',headers=h(fh+'.'+parts[1]+'.')); rec('JWT alg:none rejected',r.status_code==401,f'HTTP {r.status_code}')
  try:
   p=json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4))); p['sub']='999999999'; fp=base64.urlsafe_b64encode(json.dumps(p,separators=(',',':')).encode()).decode().rstrip('='); r=req('GET','/documents',headers=h(parts[0]+'.'+fp+'.'+parts[2])); rec('JWT payload tampering rejected',r.status_code==401,f'HTTP {r.status_code}')
  except Exception as e: rec('JWT payload tampering rejected',False,str(e))
 else: rec('JWT alg:none rejected',False,'Unexpected JWT format'); rec('JWT payload tampering rejected',False,'Unexpected JWT format')
 fn='security_audit_'+uuid.uuid4().hex[:8]+'.txt'; content=b'NexusAI security audit test.\n'
 r=req('POST','/upload',headers=h(token),files={'file':(fn,content,'text/plain')}); rec('Authenticated upload accepted',r.status_code==200,f'HTTP {r.status_code}')
 r=req('GET','/documents',headers=h(token)); rec('Authenticated documents listing allowed',r.status_code==200,f'HTTP {r.status_code}')
 r=req('POST','/upload',headers=h(token),files={'file':('../nexusai_escape.txt',b'escape','text/plain')}); rec('Upload traversal rejected',r.status_code in (400,415),f'HTTP {r.status_code}')
 r=req('GET','/documents/%2e%2e%2fauth.db%2ffile',headers=h(token)); rec('Encoded traversal blocked',r.status_code!=200,f'HTTP {r.status_code}')
 r=req('POST','/upload',headers=h(token),files={'file':('security_audit.exe',b'MZfake','application/octet-stream')}); rec('Executable upload rejected',r.status_code==415,f'HTTP {r.status_code}')
 r=req('POST','/upload',headers=h(token),files={'file':('security_audit_fake.pdf',b'MZnot-a-pdf','application/pdf')}); rec('Fake PDF rejected',r.status_code==415,f'HTTP {r.status_code}')
 r=req('POST','/upload',headers=h(token),files={'file':('security_audit_oversize.txt',b'x'*(15*1024*1024+1),'text/plain')},timeout=45); rec('15MB upload limit enforced',r.status_code==413,f'HTTP {r.status_code}')
 leak='security_audit_error_'+uuid.uuid4().hex[:8]+'.txt'; r=req('POST','/upload',headers=h(token),files={'file':(leak,b'a'*(10*1024*1024),'text/plain')},timeout=90); body=r.text.lower(); bad=['traceback','batch size','valueerror:','filenotfounderror','permissionerror','sqlalchemy','sqlite3','errno ']; rec('Upload error hides internals',not any(x in body for x in bad),f'HTTP {r.status_code}')
 r=req('POST','/chat',headers=h(token),json={'question':'security audit','filenames':[leak]}); body=r.text.lower(); rec('Chat error hides internals',not any(x in body for x in bad),f'HTTP {r.status_code}')
 r=req('OPTIONS','/documents',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'GET'}); rec('Allowed CORS origin accepted',r.status_code==200 and r.headers.get('access-control-allow-origin')=='http://localhost:5173',f"HTTP {r.status_code}")
 r=req('OPTIONS','/documents',headers={'Origin':'http://evil.example','Access-Control-Request-Method':'GET'}); rec('Untrusted CORS origin rejected',r.headers.get('access-control-allow-origin')!='http://evil.example',f'HTTP {r.status_code}')
 r=req('POST','/documents',headers=h(token)); rec('Unsupported HTTP method rejected',r.status_code==405,f'HTTP {r.status_code}')
 r=req('POST','/reset-password',json={'email':'securitytest_77b2273c@nexusai.com','otp':'000000','new_password':'x'}); rec('Weak reset password rejected',r.status_code==400,f'HTTP {r.status_code}')
 for x in (fn,leak):
  try:req('DELETE','/documents/'+x,headers=h(token))
  except:pass
 summary(); return 0 if not any(not x[1] for x in results) else 1
def summary():
 p=sum(x[1] for x in results); f=len(results)-p; print('\n'+'='*62); print(f'Total: {len(results)} | Passed: {p} | Failed: {f}');
 if f:
  print('FAILED CHECKS:'); [print(' -',n,d) for n,o,d in results if not o]
 print('Overall:', 'SECURITY AUDIT PASS' if f==0 else 'SECURITY AUDIT NEEDS REVIEW'); print('='*62)
if __name__=='__main__': sys.exit(main())
