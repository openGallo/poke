"""Actual local browser/HTTP tests; isolated synthetic records, no provider requests.
Run: python scripts/conditions_ui_checks.py /tmp/ember-v21-ui
"""
import json, os, shutil, socket, sys, tempfile, threading, time
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
import uvicorn
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright,expect
from fastapi.testclient import TestClient
from ember.config import Config
from ember.main import create_app
from ember.security import PH

RAW='raw:seller:Near Mint';PSA10='graded:PSA:10:Gem Mint:current'

def run(output,offline=False):
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 result={'environment':'Local Chromium over actual HTTP to isolated Uvicorn/SQLite; external network requests blocked; NOT a public deployment or live-provider test. All fixtures synthetic.','checks':[],'js_errors':[]}
 if offline: result['environment']='Offline Chromium components + isolated in-process ASGI bridge; NOT browser-network or deployed end-to-end verification. External image requests blocked; all fixtures synthetic.'
 def passed(text): result['checks'].append({'check':text,'passed':True});print('PASS',text,flush=True)
 with tempfile.TemporaryDirectory(prefix='ember-conditions-ui-') as temp:
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  origin=f'http://127.0.0.1:{port}';password='Synthetic condition UI testing only'
  config=Config(data_dir=Path(temp)/'runtime',password_hash=PH.hash(password),encryption_key=Fernet.generate_key().decode(),public_url=origin,scheduler=False)
  app=create_app(config);server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error'))
  thread=threading.Thread(target=server.run,daemon=True);thread.start()
  try:
   with httpx.Client(base_url=origin,timeout=10) as api:
    for _ in range(100):
     try:
      if api.get('/healthz').status_code==200:break
     except httpx.HTTPError:pass
     time.sleep(.05)
    with sync_playwright() as pw:
     browser=pw.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
     bridge=TestClient(app,base_url=origin)
     static=Path(__file__).resolve().parents[1]/'ember/static'
     def transport(path,method,body,headers):
      if not path.startswith('/api/'):raise ValueError('Only the isolated application API is allowed')
      r=bridge.request(method,path,content=body,headers=headers)
      return {'status':r.status_code,'text':r.text}
     def new_page():
      page=browser.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(6000)
      page.on('pageerror',lambda e:result['js_errors'].append(str(e)))
      if offline:
       page.route('**/*',lambda r:r.abort())
       page.expose_function('emberTestTransport',transport)
       page.set_content('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><dialog id="modal"><div id="modal-content"></div></dialog><div id="toast" role="status" aria-live="polite"></div></body></html>')
       page.add_style_tag(content=(static/'style.css').read_text())
       page.evaluate('''() => {window.fetch=async(path,options={})=>{const r=await window.emberTestTransport(path,options.method||'GET',options.body||null,options.headers||{});return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>JSON.parse(r.text)};};}''')
       page.add_script_tag(content=(static/'app.js').read_text(),type='module')
      else:
       page.route('**/*',lambda r:r.continue_() if r.request.url.startswith(origin+'/') else r.abort())
       page.goto(origin,wait_until='networkidle')
      return page
     def go_card():
      if offline:page.evaluate('(id)=>location.hash="card/"+id',card['id'])
      else:page.goto(origin+'/#card/'+card['id'])
     page=new_page()
     try:
      expect(page.get_by_role('heading',name='Welcome to your binder.')).to_be_visible()
      page.get_by_label('Owner password').fill(password)
      page.get_by_role('button',name='Open collection').click()
      expect(page.get_by_role('heading',name='Your collection, in perspective.')).to_be_visible()
      expect(page.get_by_text('PSA 10 COMPLETION',exact=True)).to_be_visible()
      page.screenshot(path=str(output/'dashboard-desktop.png'),full_page=True)
      passed('Private-session login and empty dual-completion dashboard render')
      login=api.post('/api/login',json={'password':password}).json();api.headers['X-CSRF-Token']=login['csrf']
      state=api.get('/api/state').json()
      card=next(v for v in state['variants'] if v['set_code']=='base1' and v['language']=='en' and v['print_run']=='standard' and v['edition']=='unlimited' and v['size']=='standard')
      go_card()
      expect(page.get_by_role('heading',name='Buy this card')).to_be_visible()
      expect(page.get_by_text('External searches, not verified listings or scanned prices.')).to_be_visible()
      passed('Card detail shows buying comparison and labelled external research searches')
      page.get_by_role('button',name='Refresh free public guides',exact=True).click()
      expect(page.get_by_role('dialog')).to_be_visible()
      expect(page.get_by_label('TCGdex card ID',exact=True)).to_have_value('base1-46')
      assert not page.get_by_role('dialog').get_by_role('checkbox').is_checked()
      page.get_by_role('dialog').get_by_role('button',name='Cancel',exact=True).click()
      passed('Free public-guide mapping form makes review explicit without provider or subscription requests')
      page.get_by_role('button',name='Record a copy',exact=True).click()
      page.get_by_label('Condition / grading category',exact=True).select_option(RAW)
      page.get_by_label('Original condition wording / slab description').fill('Near Mint')
      page.get_by_label('Seller',exact=True).fill('SYNTHETIC UI TEST ONLY')
      page.get_by_label('I verified the exact printing and the recorded condition or grade.').check()
      page.get_by_role('dialog').get_by_role('button',name='Save',exact=True).click()
      expect(page.get_by_role('dialog')).not_to_be_visible()
      expect(page.get_by_text('Owned as an alternative — PSA 10 still missing. Upgrade monitoring continues.')).to_be_visible()
      s=api.get('/api/state').json();assert s['completion']['owned']==0 and s['completion']['any_owned']==1
      if offline:
       page.close();page=new_page();expect(page.get_by_role('heading',name='Your collection, in perspective.')).to_be_visible();go_card()
      else:page.reload()
      expect(page.get_by_text('SYNTHETIC UI TEST ONLY',exact=False)).to_be_visible()
      passed('Raw ownership form persists through browser component reload without completing PSA 10')
      page.get_by_role('button',name='Set a target',exact=True).click()
      page.get_by_label('Target condition / grade',exact=True).select_option(RAW)
      page.get_by_label('Delivered-price target (optional)').fill('25')
      page.get_by_role('dialog').get_by_role('button',name='Save',exact=True).click()
      expect(page.get_by_role('dialog')).not_to_be_visible()
      assert api.get('/api/cards/'+card['id']).json()['watch']['targets'][RAW]==25
      passed('Condition-specific target saves through the watchlist form')
      page.get_by_role('button',name='Add a listing',exact=True).click()
      page.get_by_label('Condition / grading category',exact=True).select_option(RAW)
      page.get_by_label('Original condition wording / slab description').fill('Near Mint')
      page.get_by_label('Exact listing title').fill('Charmander 46/102 Base Set Unlimited English raw Near Mint — SYNTHETIC TEST')
      page.get_by_label('Direct listing URL').fill('https://example.com/synthetic-ui-raw-offer')
      page.get_by_label('Item asking price / current bid').fill('20')
      for name in ['Shipping (blank = unknown)','Fees (blank = unknown)','Import cost (blank = unknown)']:page.get_by_label(name,exact=True).fill('0')
      page.get_by_label('Delivery eligibility',exact=True).select_option('true')
      page.get_by_role('dialog').get_by_role('button',name='Save',exact=True).click()
      expect(page.get_by_role('dialog')).not_to_be_visible()
      page.get_by_role('button',name='Review exact card',exact=True).click()
      page.get_by_label('What did you check?').fill('SYNTHETIC test checks, not an actual sale or authenticity statement.')
      for checkbox in page.get_by_role('dialog').get_by_role('checkbox').all():checkbox.check()
      page.get_by_role('button',name='Save review',exact=True).click()
      expect(page.get_by_role('dialog')).not_to_be_visible()
      passed('Raw listing entry, explicit delivery costs and condition review reach the actual application backend')
      page.get_by_role('button',name='Add a sale',exact=True).click()
      page.get_by_label('Condition / grading category',exact=True).select_option(RAW)
      page.get_by_label('Source',exact=True).fill('SYNTHETIC TEST EVIDENCE')
      page.get_by_label('Evidence URL').fill('https://example.com/synthetic-ui-raw-sale')
      page.get_by_label('Sold date').fill(date.today().isoformat())
      page.get_by_label('Disclosed item price (not shipping)').fill('30')
      for checkbox in page.get_by_role('dialog').get_by_role('checkbox').all():checkbox.check()
      page.get_by_role('dialog').get_by_role('button',name='Save',exact=True).click()
      expect(page.get_by_role('dialog')).not_to_be_visible()
      page.get_by_label('Historical condition / grade',exact=True).select_option(RAW)
      expect(page.get_by_text('1 eligible sales',exact=True)).to_be_visible()
      expect(page.locator('#condition-history').get_by_text('Need 5 eligible sales',exact=False)).to_be_visible()
      expect(page.locator('#condition-history > figure').first.locator('svg circle')).to_have_count(1)
      passed('Real sale observation is bucketed correctly; one sale remains insufficient and is plotted as one point')
      # Switching to PSA does not inherit raw sales.
      page.get_by_label('Historical condition / grade',exact=True).select_option(PSA10)
      expect(page.get_by_text('0 eligible sales',exact=True)).to_be_visible()
      page.get_by_role('button',name='Scan this card',exact=True).click()
      expect(page.get_by_text('paused: Saved pause state honored.',exact=False)).to_be_visible()
      passed('PSA history stays separate and per-card refresh visibly respects pause')
      page.get_by_role('link',name='Settings',exact=True).click()
      expect(page.get_by_role('heading',name='PSA 10 & fallback buying preferences')).to_be_visible()
      page.get_by_label('Total collection budget (optional)').fill('500')
      page.get_by_label('Allowed fallback categories',exact=False).select_option([RAW,'graded:PSA:9:Mint:current'])
      page.get_by_label('Minimum seller positive feedback (%) — optional',exact=True).fill('98')
      page.get_by_label('Allowed seller countries (comma-separated; blank = all)',exact=True).fill('BE, FR')
      page.get_by_role('button',name='Save preferences',exact=True).click()
      expect(page.get_by_text('Preferences saved.',exact=True)).to_be_visible()
      p=api.get('/api/state').json()['preferences'];assert p['seller_countries']==['BE','FR'] and p['min_seller_feedback']==98 and RAW in p['fallback_buckets']
      passed('Global fallback, seller and budget preferences save and reload')
      page.get_by_role('link',name='Buying opportunities',exact=False).click()
      expect(page.get_by_role('heading',name='Buying opportunities.')).to_be_visible()
      page.get_by_label('Grader / raw',exact=True).select_option('RAW')
      expect(page.get_by_text('No matching buying opportunities',exact=False)).to_be_visible()
      passed('Deals filters operate; an already-owned fallback is not another collection need')
      page.set_viewport_size({'width':390,'height':844})
      page.get_by_role('link',name='The collection',exact=True).click()
      expect(page.get_by_role('heading',name='The collection.')).to_be_visible()
      assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
      page.screenshot(path=str(output/'binder-mobile.png'),full_page=True)
      passed('390-pixel binder has no page-level horizontal overflow')
      go_card();expect(page.get_by_role('heading',name='Buy this card')).to_be_visible()
      assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
      page.screenshot(path=str(output/'buying-mobile-synthetic-test.png'),full_page=True)
      passed('390-pixel card comparison and condition history have no page-level overflow')
      page.get_by_role('link',name='Settings',exact=True).click()
      expect(page.get_by_role('heading',name='Source capability inventory')).to_be_visible()
      assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
      passed('390-pixel settings and source capability inventory have no page-level overflow')
      assert not result['js_errors'],result['js_errors']
      passed('No uncaught browser JavaScript errors in checked workflows')
     except Exception:
      page.screenshot(path=str(output/'failure.png'),full_page=True)
      (output/'failure-dom.txt').write_text(page.locator('body').inner_text())
      raise
     finally: browser.close()
  finally:
   server.should_exit=True;thread.join(timeout=10)
   (output/'ui-results.json').write_text(json.dumps(result,indent=2))
 return result

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('output',nargs='?',default='/tmp/ember-v21-ui')
 parser.add_argument('--offline-bridge',action='store_true',help='Test browser components over an isolated ASGI bridge, not browser networking')
 args=parser.parse_args()
 run(args.output,offline=args.offline_bridge)
