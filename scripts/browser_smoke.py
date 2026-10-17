#!/usr/bin/env python3
"""Run real Chromium smoke checks against an isolated temporary SQLite database.
Usage: python scripts/browser_smoke.py [--artifacts artifacts]
Never calls a paid provider or a social platform.
"""
from __future__ import annotations
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from PIL import Image
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--artifacts',default='artifacts')
    parser.add_argument('--transport',choices=['network','inprocess'],default='network',help='inprocess: offline browser UI with real FastAPI TestClient; no browser network access')
    args=parser.parse_args()
    artifacts=Path(args.artifacts).resolve();artifacts.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='creative-loop-smoke-') as data:
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        env={**os.environ,'DATA_DIR':data,'ALLOW_EXTERNAL_AI':'0','OPENAI_API_KEY':'','APP_TOKEN':'','ALLOWED_HOSTS':'127.0.0.1,localhost'}
        log=open(artifacts/'server.log','w')
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','creative_loop.app:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
        checks=[]
        try:
            base=f'http://127.0.0.1:{port}'
            for _ in range(100):
                try:
                    urllib.request.urlopen(base+'/api/health',timeout=1).close();break
                except Exception:time.sleep(.1)
            else:raise RuntimeError('Server failed to start')
            with sync_playwright() as p:
                executable=os.getenv('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
                browser=p.chromium.launch(headless=True,executable_path=executable,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1600,'height':1100},device_scale_factor=1,accept_downloads=True)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                if args.transport == 'inprocess':
                    from unittest.mock import patch
                    sys.path.insert(0,str(ROOT))
                    from fastapi.testclient import TestClient
                    from creative_loop.app import create_app
                    with patch.dict(os.environ, {'APP_TOKEN':'','ALLOW_EXTERNAL_AI':'0'}):
                        api_client=TestClient(create_app(data))
                    import base64
                    def bridge(req):
                        options={'headers':req.get('headers',{})}
                        if req.get('files'):
                            options['files']=[(f['field'],(f['filename'],base64.b64decode(f['body']),f['type'])) for f in req['files']]
                            options['data']=req.get('fields',{})
                        elif 'body' in req:
                            options['content']=req['body']
                        with patch.dict(os.environ, {'APP_TOKEN':'','ALLOW_EXTERNAL_AI':'0','ALLOWED_HOSTS':'127.0.0.1,localhost,testserver,::1'}):
                            r=api_client.request(req.get('method','GET'),req['url'],**options)
                        return {'status':r.status_code,'headers':dict(r.headers),'body':base64.b64encode(r.content).decode()}
                    page.expose_function('__apiBridge',bridge)
                    html=(ROOT/'creative_loop/static/index.html').read_text()
                    html=html.replace('<link rel="stylesheet" href="/static/style.css">','<style>'+(ROOT/'creative_loop/static/style.css').read_text()+'</style>')
                    html=html.replace('<script src="/static/app.js" defer></script>','')
                    page.set_content(html)
                    page.add_script_tag(content=r"""
                    Object.defineProperty(window,'sessionStorage',{value:{getItem:()=> 'offline-ui-harness',setItem:()=>{}}});
                    window.fetch=async (url,options={})=>{
                      const req={url:String(url),method:options.method||'GET',headers:options.headers||{}};
                      if(options.body instanceof FormData){
                        req.fields={};req.files=[];
                        for(const [k,v] of options.body.entries()){
                          if(v instanceof File){const bytes=new Uint8Array(await v.arrayBuffer());let binary='';for(const b of bytes)binary+=String.fromCharCode(b);req.files.push({field:k,filename:v.name,type:v.type,body:btoa(binary)});}
                          else req.fields[k]=v;
                        }
                      }else if(options.body)req.body=options.body;
                      const r=await window.__apiBridge(req);
                      return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:r.headers});
                    };
                    """)
                    page.add_script_tag(content=(ROOT/'creative_loop/static/app.js').read_text())
                    page.wait_for_timeout(200)
                else:
                    page.goto(base,wait_until='networkidle')
                expect(page.locator('.empty-state')).to_be_visible()
                page.locator('#generateBtn').click()
                expect(page.locator('.creative-card')).to_have_count(12)
                expect(page.locator('#editRevision')).to_have_text('v1')
                checks.append('Generate 12 variants in browser')
                page.locator('#editHeadline').fill('오늘의 리듬, 새롭게')
                page.locator('#editForm button[type=submit]').click()
                expect(page.locator('#editRevision')).to_have_text('v2')
                checks.append('Edit headline and persist revision')
                page.locator('[data-compare]').nth(0).check();page.locator('[data-compare]').nth(1).check()
                page.locator('#compareBtn').click()
                expect(page.locator('#compareDialog')).to_be_visible()
                page.locator('#choiceReason').fill('테스트: 첫 번째 레이아웃을 선택')
                page.locator('[data-winner]').nth(0).click()
                expect(page.locator('#compareDialog')).not_to_be_visible()
                checks.append('Pairwise preference persisted')
                page.locator('[data-star]').nth(0).click()
                expect(page.locator('.star.selected')).to_have_count(1)
                with page.expect_download() as info:page.locator('#pngBtn').click()
                info.value.save_as(artifacts/'export-test.png')
                with Image.open(artifacts/'export-test.png') as im:assert im.size==(1080,1080)
                checks.append('Browser PNG export at 1080 x 1080')
                with page.expect_download() as info:page.locator('#exportBtn').click()
                info.value.save_as(artifacts/'selected-export-test.zip')
                import zipfile
                with zipfile.ZipFile(artifacts/'selected-export-test.zip') as z:assert len([n for n in z.namelist() if n.endswith('.svg')])==1
                checks.append('Selected SVG + JSON ZIP export')
                page.wait_for_timeout(300)
                page.locator('#toast').evaluate('(el)=>el.hidden=true')
                page.screenshot(path=str(artifacts/'studio-desktop.png'),full_page=True)
                page.locator('[data-tab=library]').click()
                page.locator('#openUploadBtn').click()
                image=io.BytesIO();Image.new('RGB',(600,400),'#d93838').save(image,'PNG')
                page.locator('#imageFile').set_input_files({'name':'test-image.png','mimeType':'image/png','buffer':image.getvalue()})
                page.locator('#uploadRights').fill('직접 제작한 자동화 테스트용 이미지')
                page.locator('#assetGeneration').check()
                page.locator('#uploadForm button[type=submit]').click()
                expect(page.locator('.asset-item')).to_have_count(1)
                checks.append('Image upload + automatic pixel features')
                page.locator('#importFile').set_input_files(str(ROOT/'examples/demo-observations.json'))
                expect(page.locator('#observationRows tr')).to_have_count(6)
                expect(page.locator('.demo-badge')).to_have_count(6)
                checks.append('JSON reaction import with explicit DEMO labels')
                page.locator('#toast').evaluate('(el)=>el.hidden=true')
                page.screenshot(path=str(artifacts/'library-desktop.png'),full_page=True)
                page.locator('[data-tab=history]').click()
                expect(page.locator('.history-card')).to_have_count(1)
                page.locator('.history-card').click()
                expect(page.locator('.creative-card')).to_have_count(12)
                checks.append('History reopens persisted batch')
                page.set_viewport_size({'width':390,'height':844})
                page.locator('.workspace').scroll_into_view_if_needed()
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile horizontal overflow'
                page.screenshot(path=str(artifacts/'studio-mobile.png'),full_page=True)
                checks.append('390px mobile layout without horizontal overflow')
                assert not errors, errors
                checks.append('No browser JavaScript exceptions')
                browser.close()
            result={'status':'passed','transport':args.transport,'checks':checks,'count':len(checks),'provider_live_calls':0,'database':'temporary; discarded after test'}
            (artifacts/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
            print(json.dumps(result,ensure_ascii=False,indent=2))
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            log.close()

if __name__=='__main__':main()
