"""Real local HTTP process, restart persistence and scheduler verification.
Temporary credentials and slab records are synthetic, not production data.
"""
import json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from cryptography.fernet import Fernet
from ember.security import PH


def run(output):
    result={'environment':'Actual Uvicorn loopback HTTP process; isolated temporary database; synthetic records only','checks':[]}
    def passed(text):result['checks'].append({'check':text,'passed':True});print('PASS',text,flush=True)
    with tempfile.TemporaryDirectory(prefix='ember-http-test-') as temp:
        root=Path(temp);data=root/'runtime';data.mkdir(mode=0o700)
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        origin=f'http://127.0.0.1:{port}';password='Synthetic HTTP-process test password'
        cfg={'password_hash':PH.hash(password),'encryption_key':Fernet.generate_key().decode(),'public_url':origin,'monitor_token':'synthetic-http-service-token'}
        (data/'config.json').write_text(json.dumps(cfg));(data/'config.json').chmod(0o600)
        env=os.environ|{'EMBER_DATA_DIR':str(data),'EMBER_SCHEDULER':'true'}
        log=open(root/'server.log','w+');process=None
        def start():
            proc=subprocess.Popen([sys.executable,'-m','ember','serve','--port',str(port)],env=env,stdout=log,stderr=log,cwd=Path(__file__).resolve().parents[1])
            for _ in range(100):
                try:
                    if httpx.get(origin+'/healthz',timeout=1).status_code==200:return proc
                except httpx.HTTPError:pass
                time.sleep(.1)
            proc.terminate();raise RuntimeError('Server did not start')
        try:
            process=start()
            with httpx.Client(base_url=origin,timeout=15) as client:
                assert client.get('/api/state').status_code==401
                login=client.post('/api/login',json={'password':password});assert login.status_code==200
                client.headers['X-CSRF-Token']=login.json()['csrf']
                state=client.get('/api/state').json();assert not state['copies']
                passed('Server starts, rejects anonymous collection access and permits owner login')
                v=next(x for x in state['variants'] if x['identity_status']=='documented')
                saved=client.post('/api/copies',json={'variant_id':v['id'],'cert':'90000009','psa10_confirmed':True,'notes':'SYNTHETIC HTTP TEST ONLY'});assert saved.status_code==200
                process.terminate();process.wait(timeout=10);process=start()
                state=client.get('/api/state').json();assert len(state['copies'])==1 and state['copies'][0]['cert']=='90000009'
                passed('Owned slab and session survive full OS-process stop and restart')
                assert client.delete('/api/copies/'+saved.json()['id']).status_code==200
                assert not client.get('/api/state').json()['copies']
                passed('Synthetic slab removed and collection restored to zero ownership')
                posted=client.post('/api/monitor',json={'force':True}).json();proof=client.get('/api/monitor').json()
                assert posted['status']=='paused' and proof['last_execution']['checkedAt']==posted['checkedAt']
                result['manual_monitor']={'checkedAt':posted['checkedAt'],'status':posted['status']}
                passed('POST updater execution exactly matches persisted GET timestamp and respects pause')
                deadline=time.monotonic()+80;scheduled=None
                while time.monotonic()<deadline:
                    scheduled=next((r for r in client.get('/api/monitor').json()['history'] if r['trigger']=='scheduled'),None)
                    if scheduled:break
                    time.sleep(1)
                assert scheduled and scheduled['status']=='paused'
                result['observed_scheduled_execution']=scheduled
                passed('Production 60-second scheduler actually wakes and persists its paused execution')
                prefs=client.get('/api/state').json()['preferences'];prefs['paused']=False
                assert client.put('/api/settings',json=prefs).status_code==200
                missing=client.post('/api/monitor',json={'force':True}).json()
                assert missing['status']=='missing_credentials' and missing['scanned_variants']==0
                passed('Unconfigured eBay reports missing credentials with zero fabricated scan results')
            subprocess.run([sys.executable,'-m','ember','backup',str(root/'private-backup.sqlite3')],env=env,check=True,cwd=Path(__file__).resolve().parents[1],capture_output=True)
            passed('Consistent SQLite backup completes and passes integrity verification')
        finally:
            if process:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            log.close();output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2))
    return result

if __name__=='__main__':run(Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/ember-http-results.json'))
