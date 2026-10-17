"""Contract tests use generated fixtures and HTTP mocks, never live model calls."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from creative_loop import providers
from creative_loop.app import create_app
from creative_loop.models import ImageRequest
from creative_loop.store import Store


def png_bytes():
    stream=io.BytesIO(); Image.new('RGB',(80,60),'#336699').save(stream,'PNG'); return stream.getvalue()


@pytest.fixture
def configured(tmp_path,monkeypatch):
    monkeypatch.setenv('ALLOW_EXTERNAL_AI','1')
    monkeypatch.setenv('OPENAI_API_KEY','test-not-real')
    monkeypatch.setenv('OPENAI_IMAGE_MODEL','test-image-model')
    monkeypatch.setenv('MAX_PROVIDER_CALLS_PER_DAY','20')
    return Store(tmp_path)


def test_image_generate_contract(configured):
    def handler(req):
        assert str(req.url)=='https://api.openai.com/v1/images/generations'
        payload=json.loads(req.content)
        assert payload['n']==1 and payload['output_format']=='png'
        assert payload['model']=='test-image-model'
        return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(png_bytes()).decode()}]})
    clean,digest,features,provenance=providers.image_create_or_edit(configured,ImageRequest(prompt='테스트 이미지'),transport=httpx.MockTransport(handler))
    assert len(clean)>0 and features['width']==80 and provenance['task']=='image_generate'


def test_image_edit_contract(configured):
    def handler(req):
        assert str(req.url)=='https://api.openai.com/v1/images/edits'
        assert 'multipart/form-data' in req.headers['content-type']
        assert b'name="image"' in req.content
        return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(png_bytes()).decode()}]})
    result=providers.image_create_or_edit(configured,ImageRequest(prompt='색을 바꾸기',asset_id='a'*32),png_bytes(),httpx.MockTransport(handler))
    assert result[3]['parent_asset_id']=='a'*32 and result[3]['task']=='image_edit'


@pytest.mark.parametrize('payload',[{'data':[]},{'data':[{'b64_json':'@not-base64'}]},{'data':[{'b64_json':base64.b64encode(b'not an image').decode()}]}])
def test_bad_image_payload_rejected(configured,payload):
    with pytest.raises(providers.ProviderError):
        providers.image_create_or_edit(configured,ImageRequest(prompt='test'),transport=httpx.MockTransport(lambda req:httpx.Response(200,json=payload)))


def test_image_error_does_not_leak_data(configured):
    with pytest.raises(providers.ProviderError) as error:
        providers.image_create_or_edit(configured,ImageRequest(prompt='test'),transport=httpx.MockTransport(lambda req:httpx.Response(401,text='private-image-secret')))
    assert 'private-image-secret' not in str(error.value)


def test_edit_requires_source(configured):
    with pytest.raises(providers.ProviderError,match='수정할 이미지'):
        providers.image_create_or_edit(configured,ImageRequest(prompt='test',asset_id='a'*32))


def test_image_shared_request_cap(configured,monkeypatch):
    monkeypatch.setenv('MAX_PROVIDER_CALLS_PER_DAY','1')
    transport=httpx.MockTransport(lambda req:httpx.Response(429))
    with pytest.raises(providers.ProviderError):providers.image_create_or_edit(configured,ImageRequest(prompt='test'),transport=transport)
    with pytest.raises(providers.ProviderError,match='호출 한도'):providers.image_create_or_edit(configured,ImageRequest(prompt='test'),transport=transport)


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.delenv('APP_TOKEN',raising=False)
    monkeypatch.setenv('ALLOW_EXTERNAL_AI','0')
    with TestClient(create_app(tmp_path),headers={'X-Creative-Loop':'1'}) as client:yield client


def test_image_api_consent_missing_source_disabled(client):
    assert client.post('/api/ai/images',json={'prompt':'test'}).status_code==403
    assert client.post('/api/ai/images',json={'prompt':'test','asset_id':'a'*32,'confirm_external_processing':True}).status_code==404
    assert client.post('/api/ai/images',json={'prompt':'test','confirm_external_processing':True}).status_code==502


def test_image_api_reuse_rights_gate(client):
    asset=client.post('/api/assets',files={'file':('test.png',png_bytes(),'image/png')},data={'rights_basis':'directly owned','allow_generation':True}).json()
    assert client.post('/api/ai/images',json={'prompt':'change','asset_id':asset['id'],'confirm_external_processing':True}).status_code==403


def test_image_api_persists_new_asset_and_embeds(client,monkeypatch):
    from creative_loop.features import extract_image
    def fake(store,request,source):
        return (*extract_image(png_bytes()),{'task':'image_generate','model':'test-only','parent_asset_id':None})
    monkeypatch.setattr(providers,'image_create_or_edit',fake)
    result=client.post('/api/ai/images',json={'prompt':'new','confirm_external_processing':True})
    assert result.status_code==201
    asset=result.json()
    assert client.get(asset['url']).status_code==200
    response=client.post('/api/batches',json={'count':1,'brief':{'asset_id':asset['id']}})
    assert response.status_code==201
    svg=client.get(response.json()['designs'][0]['svg_url']).text
    assert 'data:image/png;base64,' in svg


def importer():
    path=Path(__file__).resolve().parents[1]/'scripts/watch_imports.py'
    spec=importlib.util.spec_from_file_location('watch_imports',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_import_watcher_remembers_success_only(tmp_path):
    folder=tmp_path/'exports';folder.mkdir()
    (folder/'valid.json').write_text('[{}]')
    state=tmp_path/'state.json'
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(200,json={'inserted':1})
    with httpx.Client(base_url='http://127.0.0.1:8000',transport=httpx.MockTransport(handler)) as client:
        assert importer().import_once(folder,state,client)['imported_files']==1
        assert importer().import_once(folder,state,client)['unchanged_files']==1
    assert len(calls)==1


def test_import_watcher_retries_failed_file(tmp_path):
    folder=tmp_path/'exports';folder.mkdir();(folder/'bad.csv').write_text('bad')
    state=tmp_path/'state.json'
    with httpx.Client(base_url='http://127.0.0.1:8000',transport=httpx.MockTransport(lambda req:httpx.Response(422))) as client:
        assert importer().import_once(folder,state,client)['failed_files']==1
    assert not state.exists()


def test_import_watcher_changed_file_reprocessed(tmp_path):
    folder=tmp_path/'exports';folder.mkdir();path=folder/'valid.json';path.write_text('[{}]')
    state=tmp_path/'state.json'
    with httpx.Client(base_url='http://127.0.0.1:8000',transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'inserted':1}))) as client:
        assert importer().import_once(folder,state,client)['imported_files']==1
        path.write_text('[{},{}]')
        assert importer().import_once(folder,state,client)['imported_files']==1


def test_import_watcher_skips_symlink(tmp_path):
    folder=tmp_path/'exports';folder.mkdir();real=tmp_path/'outside.json';real.write_text('[{}]')
    (folder/'linked.json').symlink_to(real)
    with httpx.Client(base_url='http://127.0.0.1:8000',transport=httpx.MockTransport(lambda req:pytest.fail('Must not send symlink contents'))) as client:
        assert importer().import_once(folder,tmp_path/'state.json',client)['imported_files']==0
