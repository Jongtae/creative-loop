import io
import json
import zipfile
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from creative_loop.app import create_app
from creative_loop.design import generate_specs, render_svg
from creative_loop.models import Brief, DesignSpec, GenerateRequest
from creative_loop.features import contrast, event_rates, eligible_cohort, extract_image, preference_weights, redact_comment


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('APP_TOKEN', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('ALLOW_EXTERNAL_AI', raising=False)
    with TestClient(create_app(tmp_path), headers={'X-Creative-Loop':'1'}) as c:
        yield c


def observation(**updates):
    now = datetime.now(timezone.utc)
    return {'source_id':'owned-1', 'platform':'owned', 'title':'Test creative',
            'published_at':(now-timedelta(days=7)).isoformat(), 'observed_at':now.isoformat(),
            'impressions':1000, 'likes':20, 'shares':5, 'comments_count':2,
            'palette':['#FFFFFF','#D93838'], 'layout':'split',
            'rights_basis':'Owned work and permission for analysis', 'allow_analysis':True,
            'allow_generation':True, **updates}


def batch(client, **kwargs):
    r = client.post('/api/batches', json=kwargs)
    assert r.status_code == 201, r.text
    return r.json()


def png_bytes():
    out=io.BytesIO();Image.new('RGB',(320,180),'#d93838').save(out,'PNG');return out.getvalue()


def upload(client, allowed=True):
    r=client.post('/api/assets',files={'file':('test.png',png_bytes(),'image/png')},
                  data={'rights_basis':'직접 제작한 테스트 이미지','allow_generation':str(allowed).lower()})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_and_ui(client):
    assert client.get('/api/health').json()['capabilities']['sns_auto_collection'] is False
    r=client.get('/');assert r.status_code==200 and 'Creative Loop' in r.text
    assert "frame-ancestors 'none'" in r.headers['Content-Security-Policy']


def test_requires_write_header(client):
    r=client.post('/api/batches',json={},headers={'X-Creative-Loop':''})
    assert r.status_code==403


def test_cross_origin_write_rejected(client):
    r=client.post('/api/batches',json={},headers={'Origin':'https://evil.example'})
    assert r.status_code==403


def test_host_rejected(client):
    assert client.get('/api/health',headers={'host':'evil.example'}).status_code==400


def test_api_token(client,monkeypatch):
    monkeypatch.setenv('APP_TOKEN','local-test-secret')
    assert client.get('/api/health').status_code==401
    assert client.get('/api/health',headers={'Authorization':'Bearer local-test-secret'}).status_code==200


def test_generation_has_60_distinct_specs():
    req=GenerateRequest(count=60,brief=Brief(palette=['#FFFFFF','#111111']))
    a,_=generate_specs(req,[]);b,_=generate_specs(req,[])
    assert len(a)==60 and a==b
    assert len({d.model_dump_json() for d in a})==60
    assert len({d.layout for d in a[:6]})==6


def test_generated_svg_parse_and_escape(client):
    r=batch(client,brief={'headline':'<script>alert(1)</script> & 안녕'})
    d=r['designs'][0];svg=client.get(d['svg_url']).text
    ElementTree.fromstring(svg)
    assert '<script>' not in svg and '&lt;script&gt;' in svg
    assert d['scores']['customer_preference_prediction'] is None


@pytest.mark.parametrize('fmt',['square','portrait','landscape'])
@pytest.mark.parametrize('layout',['editorial','split','poster','frame','orbit','stack'])
def test_all_layout_formats(fmt,layout):
    svg=render_svg(Brief(format=fmt,headline='브랜드의 이야기를 명확하게 전달하는 디자인입니다 '*3),
                   DesignSpec(layout=layout,background='#FFFFFF',foreground='#111111',accent='#AA1122'))
    root=ElementTree.fromstring(svg)
    assert int(root.attrib['width'])>0
    assert root.findall('.//{http://www.w3.org/2000/svg}text')


def test_bounds_and_unknown_fields(client):
    assert client.post('/api/batches',json={'count':61}).status_code==422
    assert client.post('/api/batches',json={'brief':{'palette':['javascript:evil','#111111']}}).status_code==422
    assert client.post('/api/batches',json={'brief':{'secret':'injected'}}).status_code==422


def test_upload_extract_and_strip(client):
    a=upload(client);assert a['features']['width']==320 and a['features']['height']==180
    assert a['features']['palette'][0]=='#D93838'
    assert a['features']['semantic_analysis'] is None
    assert client.get(a['url']).headers['content-type']=='image/png'


def test_image_format_rejected(client):
    r=client.post('/api/assets',files={'file':('bad.svg',b'<svg/>','image/svg+xml')},data={'rights_basis':'owned image'})
    assert r.status_code==422


def test_image_generation_rights_enforced(client):
    a=upload(client,False)
    assert client.post('/api/batches',json={'brief':{'asset_id':a['id']}}).status_code==403


def test_upload_reused_in_svg(client):
    a=upload(client)
    b=batch(client,brief={'asset_id':a['id']},count=1)
    assert 'data:image/png;base64,' in client.get(b['designs'][0]['svg_url']).text
    assert client.delete('/api/assets/'+a['id']).status_code==409


def test_import_atomic_validation(client):
    good=observation();bad=observation(source_id='bad',allow_analysis=False)
    assert client.post('/api/observations/import',json=[good,bad]).status_code==422
    assert len(client.get('/api/observations').json())==0


def test_import_idempotent_and_missing_metrics(client):
    o=observation(shares=None)
    assert client.post('/api/observations/import',json=[o]).json()['inserted']==1
    assert client.post('/api/observations/import',json=[o]).json()['duplicates']==1
    row=client.get('/api/observations').json()[0]
    assert row['shares'] is None and 'shares' not in row['rates']['events_per_1000']
    assert row['rates']['events_per_1000']['likes']==20


def test_no_exposure_means_no_rate():
    assert event_rates({'likes':100})['event_sum_per_1000'] is None
    assert event_rates({'likes':0,'impressions':100})['events_per_1000']['likes']==0


def test_comment_redaction(client):
    o=observation(comments=['문의 @private_user me@example.com 010-1234-5678'])
    client.post('/api/observations/import',json=[o])
    text=client.get('/api/observations').json()[0]['comments'][0]
    assert 'me@example.com' not in text and '010-1234' not in text and '@private_user' not in text


def test_timezone_and_future_rejected(client):
    assert client.post('/api/observations/import',json=[observation(observed_at='2025-01-01T00:00:00')]).status_code==422
    assert client.post('/api/observations/import',json=[observation(observed_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())]).status_code==422


def test_invalid_json_and_csv(client):
    assert client.post('/api/observations/import',content='{bad',headers={'Content-Type':'application/json'}).status_code==422
    assert client.post('/api/observations/import-file',files={'file':('x.csv',b'garbage\nx','text/csv')}).status_code==422


def test_import_file_json(client):
    r=client.post('/api/observations/import-file',files={'file':('x.json',json.dumps([observation()]).encode(),'application/json')})
    assert r.status_code==200 and r.json()['inserted']==1


def test_evidence_excludes_demo_and_mixed_cohorts(client):
    records=[observation(source_id=str(i),likes=10+i) for i in range(3)]
    records.append(observation(source_id='demo',is_demo=True,likes=10000))
    records.append(observation(source_id='paid',traffic='paid',likes=10000))
    records.append(observation(source_id='differentwindow',window_hours=24,likes=10000))
    assert client.post('/api/observations/import',json=records).status_code==200
    result=batch(client,use_evidence=True,cohort_platform='owned')
    assert result['evidence_used']==3
    ev=result['designs'][0]['evidence'];assert len(ev)==3
    assert all(e['rate']['events_per_1000']['likes']<100 for e in ev)


def test_analysis_only_not_used_for_generation(client):
    records=[observation(source_id=str(i),allow_generation=False) for i in range(3)]
    client.post('/api/observations/import',json=records)
    result=batch(client,use_evidence=True,cohort_platform='owned')
    assert result['evidence_used']==0
    assert len(result['designs'][0]['evidence'])==3


def test_edit_revision_conflict_and_fix(client):
    d=batch(client,count=1)['designs'][0]
    body={'brief':d['brief'],'spec':{**d['spec'],'foreground':d['spec']['background']},'expected_revision':1}
    r=client.put('/api/designs/'+d['id'],json=body);assert r.status_code==200
    assert r.json()['revision']==2 and r.json()['scores']['contrast_ratio']==1
    assert client.put('/api/designs/'+d['id'],json=body).status_code==409
    fixed=client.post('/api/designs/'+d['id']+'/fix-contrast').json()
    assert fixed['scores']['contrast_ratio']>=4.5 and fixed['revision']==3
    assert len(client.get('/api/designs/'+d['id']+'/revisions').json())==2


def test_selection_and_export(client):
    b=batch(client,count=3);d=b['designs'][0]
    assert client.post('/api/designs/'+d['id']+'/select').json()['selected'] is True
    r=client.get('/api/batches/'+b['batch_id']+'/export?selected_only=true')
    z=zipfile.ZipFile(io.BytesIO(r.content))
    assert len([n for n in z.namelist() if n.endswith('.svg')])==1
    assert any(n.endswith('.json') for n in z.namelist())


def test_pairwise_learning_and_dedup(client):
    b=batch(client);ds=b['designs']
    body={'winner_id':ds[0]['id'],'loser_id':ds[1]['id']}
    for _ in range(7):assert client.post('/api/preferences',json=body).status_code==201
    d=client.get('/api/designs/'+ds[0]['id']).json()
    assert d['scores']['unique_pairs']==1 and d['scores']['designer_preference_index'] is None
    for i in range(2,7):client.post('/api/preferences',json={'winner_id':ds[0]['id'],'loser_id':ds[i]['id']})
    d=client.get('/api/designs/'+ds[0]['id']).json()
    assert d['scores']['unique_pairs']==6 and d['scores']['designer_preference_index'] is not None


def test_preference_cross_batch_rejected(client):
    a=batch(client,count=1)['designs'][0];b=batch(client,count=1)['designs'][0]
    assert client.post('/api/preferences',json={'winner_id':a['id'],'loser_id':b['id']}).status_code==422
    assert client.post('/api/preferences',json={'winner_id':a['id'],'loser_id':a['id']}).status_code==422


def test_ai_requires_consent_and_config(client):
    assert client.post('/api/ai/art-direction',json={'brief':{},'instruction':'더 간결하게'}).status_code==403
    assert client.post('/api/ai/art-direction',json={'brief':{},'instruction':'더 간결하게','confirm_external_processing':True}).status_code==502
    a=upload(client)
    assert client.post('/api/ai/vision',json={'asset_id':a['id'],'confirm_external_processing':True}).status_code==403


def test_delete_observation(client):
    client.post('/api/observations/import',json=[observation()])
    id=client.get('/api/observations').json()[0]['id']
    assert client.delete('/api/observations/'+id).status_code==200
    assert not client.get('/api/observations').json()


def test_contrast_known_values():
    assert contrast('#000000','#FFFFFF')==21
    assert contrast('#123456','#123456')==1


def test_delete_batch_cascades_and_releases_asset(client):
    a=upload(client);b=batch(client,brief={'asset_id':a['id']},count=2)
    client.post('/api/preferences',json={'winner_id':b['designs'][0]['id'],'loser_id':b['designs'][1]['id']})
    assert client.delete('/api/batches/'+b['batch_id']).status_code==200
    assert client.get('/api/health').json()['counts']['preferences']==0
    assert client.delete('/api/assets/'+a['id']).status_code==200


def test_observation_asset_palette_link(client):
    a=upload(client)
    o=observation(asset_id=a['id'],palette=[])
    assert client.post('/api/observations/import',json=[o]).status_code==200
    row=client.get('/api/observations').json()[0]
    assert row['palette'][0]=='#D93838' and row['pixel_features']['width']==320
