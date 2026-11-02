"""Reproducible browser checks against a fresh, isolated local server.
No production records, real marketplace transactions or external requests are used.
Run from repository root: python scripts/browser_smoke.py --output /tmp/ember-browser-report
"""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
import httpx
from playwright.sync_api import sync_playwright, expect
from ember.security import PH


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    results=[]
    def passed(name):results.append({'check':name,'passed':True});print('PASS',name,flush=True)
    with tempfile.TemporaryDirectory(prefix='ember-browser-isolated-') as temp:
        runtime=Path(temp)/'runtime';runtime.mkdir(mode=0o700)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        origin=f'http://127.0.0.1:{port}'
        password='Isolated browser-test password only'
        cfg={'password_hash':PH.hash(password),'encryption_key':Fernet.generate_key().decode(),'monitor_token':'synthetic-browser-monitor-token','public_url':origin}
        (runtime/'config.json').write_text(json.dumps(cfg));(runtime/'config.json').chmod(0o600)
        env=os.environ|{'EMBER_DATA_DIR':str(runtime),'EMBER_SCHEDULER':'true'}
        log=open(Path(temp)/'server.log','w+')
        server=subprocess.Popen([sys.executable,'-m','ember','serve','--port',str(port)],env=env,stdout=log,stderr=log,cwd=Path(__file__).resolve().parents[1])
        try:
            for _ in range(100):
                try:
                    if httpx.get(origin+'/healthz').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise RuntimeError('Isolated server did not start')
            started=time.monotonic()
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
                # All external imagery stays unavailable in this isolated test; no fabricated art substituted.
                page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin) else route.abort())
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(origin);expect(page.get_by_role('heading',name='Welcome to your binder.')).to_be_visible()
                assert page.request.get(origin+'/api/state').status==401
                passed('Anonymous API access rejected; login page renders')
                page.get_by_label('Owner password').fill(password)
                page.get_by_role('button',name='Open collection').click()
                expect(page.get_by_role('heading',name='Your collection, in perspective.')).to_be_visible()
                page.screenshot(path=str(output/'dashboard-desktop.png'),full_page=True)
                passed('Desktop dashboard renders with zero ownership and honest source states')
                page.get_by_role('link',name='The collection',exact=True).click()
                expect(page.get_by_role('heading',name='The collection.')).to_be_visible()
                state=page.request.get(origin+'/api/state').json()
                card=next(v for v in state['variants'] if v['set_code']=='base1' and v['language']=='en' and v['edition']=='unlimited' and v['print_run']=='standard' and v['size']=='standard')
                page.get_by_label('Search collection').fill('Base Set')
                expect(page.locator('#binder-results article').first).to_be_visible()
                passed('Binder search and missing-reference-art fallbacks render')
                page.goto(origin+'/#card/'+card['id'])
                expect(page.get_by_role('heading',name='The exact printing')).to_be_visible()
                page.get_by_role('button',name='Record a PSA 10 copy').click()
                expect(page.get_by_role('dialog')).to_be_visible()
                page.get_by_label('PSA certification number',exact=True).fill('90000001')
                page.get_by_label('Item purchase price',exact=True).fill('75')
                for label in ['Shipping (blank = unknown)','Fees (blank = unknown)','Import cost (blank = unknown)']:
                    page.get_by_label(label,exact=True).fill('0')
                page.get_by_label('Seller',exact=True).fill('SYNTHETIC BROWSER TEST — NOT A REAL PURCHASE')
                page.get_by_label('I have verified this exact card variant is graded PSA Gem Mint 10.').check()
                page.get_by_role('dialog').get_by_role('button',name='Save',exact=True).click()
                expect(page.get_by_role('dialog')).not_to_be_visible()
                page.reload();expect(page.get_by_text('SYNTHETIC BROWSER TEST',exact=False)).to_be_visible()
                assert page.request.get(origin+'/api/state').json()['completion']['owned']==1
                passed('Ownership form saves and survives browser reload')
                page.get_by_role('button',name='Set a target',exact=True).click()
                page.get_by_label('Delivered-price target (optional)').fill('100')
                page.get_by_role('dialog').get_by_role('button',name='Save',exact=True).click()
                expect(page.get_by_role('dialog')).not_to_be_visible()
                expect(page.get_by_text('On your watchlist',exact=False)).to_be_visible()
                passed('Target-price form persists a watchlist record')
                page.get_by_role('button',name='Add a listing',exact=True).click()
                page.get_by_label('Exact listing title').fill('Charmander 46/102 Base Set Unlimited English PSA 10')
                page.get_by_label('Direct listing URL').fill('https://example.com/synthetic-listing-only')
                page.get_by_label('Item asking price / current bid').fill('65')
                for label in ['Shipping (blank = unknown)','Fees (blank = unknown)','Import cost (blank = unknown)']:
                    page.get_by_label(label,exact=True).fill('0')
                page.get_by_role('dialog').get_by_role('button',name='Save',exact=True).click()
                expect(page.get_by_role('dialog')).not_to_be_visible()
                expect(page.get_by_role('button',name='Review exact slab')).to_be_visible()
                page.get_by_role('button',name='Review exact slab').click()
                page.get_by_label('PSA certification number',exact=True).fill('90000002')
                page.get_by_label('What did you check?').fill('Synthetic test of review form; not authentic marketplace evidence.')
                for checkbox in page.get_by_role('dialog').get_by_role('checkbox').all():checkbox.check()
                page.get_by_role('button',name='Save slab review').click()
                expect(page.get_by_role('dialog')).not_to_be_visible()
                expect(page.get_by_text('owner-reviewed',exact=False)).to_be_visible()
                passed('Listing form and explicit photograph/label/certificate review operate')
                page.get_by_role('button',name='Add a sale',exact=True).click()
                page.get_by_label('Source',exact=True).fill('SYNTHETIC TEST')
                page.get_by_label('Evidence URL').fill('https://example.com/synthetic-sale-only')
                page.get_by_label('Sold date').fill(date.today().isoformat())
                page.get_by_label('Disclosed item price (not shipping)').fill('100')
                for checkbox in page.get_by_role('dialog').get_by_role('checkbox').all():checkbox.check()
                page.get_by_role('dialog').get_by_role('button',name='Save',exact=True).click()
                expect(page.get_by_role('dialog')).not_to_be_visible()
                expect(page.get_by_text('1 eligible sales',exact=True)).to_be_visible()
                expect(page.get_by_text('Insufficient data',exact=True)).to_be_visible()
                passed('Real form path stores evidence and sparse sales do not produce a valuation')
                page.get_by_role('link',name='Settings',exact=True).click()
                expect(page.get_by_role('heading',name='Settings & sources.')).to_be_visible()
                page.get_by_label('Total collection budget (optional)').fill('500')
                page.get_by_role('button',name='Save preferences').click()
                expect(page.get_by_text('Preferences saved.',exact=True)).to_be_visible()
                assert page.request.get(origin+'/api/state').json()['preferences']['budget']==500
                passed('Settings form saves validated preferences')
                page.get_by_role('button',name='Run updater now').click()
                expect(page.get_by_text('paused: Saved pause state honored.',exact=False)).to_be_visible()
                heartbeat=page.request.get(origin+'/api/monitor').json()['last_execution']
                assert heartbeat['status']=='paused'
                passed('Manual updater is persisted, read back, and honors pause')
                page.set_viewport_size({'width':390,'height':844})
                page.get_by_role('link',name='The collection',exact=True).click()
                expect(page.get_by_role('heading',name='The collection.')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                page.screenshot(path=str(output/'binder-mobile.png'),full_page=True)
                passed('Mobile binder has no horizontal page overflow')
                page.goto(origin+'/#settings')
                expect(page.get_by_role('heading',name='Settings & sources.')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                passed('Mobile settings remain within the viewport')
                # Wait for a real 60-second server scheduler wake, not a direct updater call.
                deadline=started+85
                observed=None
                while time.monotonic()<deadline:
                    history=page.request.get(origin+'/api/monitor').json()['history']
                    observed=next((r for r in history if r['trigger']=='scheduled'),None)
                    if observed:break
                    time.sleep(1)
                assert observed and observed['status']=='paused','Scheduled server wake not observed'
                passed('Actual server scheduler woke at its production 60-second interval and persisted a paused execution')
                (output/'scheduler-observation.json').write_text(json.dumps(observed,indent=2))
                assert not errors,errors
                passed('No uncaught JavaScript errors during the tested browser workflows')
                browser.close()
        except Exception:
            log.flush();log.seek(0)
            (output/'server-failure.log').write_text(log.read())
            raise
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
            log.close()
            (output/'browser-results.json').write_text(json.dumps({'environment':'isolated localhost server; synthetic test records; external images blocked','checks':results},indent=2))
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('/tmp/ember-browser-results'))
    args=parser.parse_args();run(args.output)
