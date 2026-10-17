import json
import httpx
import pytest
from creative_loop import providers
from creative_loop.models import Brief
from creative_loop.store import Store

@pytest.fixture
def configured(tmp_path,monkeypatch):
    monkeypatch.setenv('ALLOW_EXTERNAL_AI','1')
    monkeypatch.setenv('OPENAI_API_KEY','test-not-a-real-key')
    monkeypatch.setenv('OPENAI_MODEL','test-model')
    monkeypatch.setenv('MAX_PROVIDER_CALLS_PER_DAY','20')
    return Store(tmp_path)


def completed(data):
    return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(data)}]}], 'usage':{'input_tokens':10,'output_tokens':20}}


def test_art_direction_contract_mock(configured):
    def handler(req):
        assert str(req.url)=='https://api.openai.com/v1/responses'
        payload=json.loads(req.content)
        assert payload['store'] is False
        assert payload['text']['format']['strict'] is True
        assert payload['model']=='test-model'
        return httpx.Response(200,json=completed({'headline':'더 명확하게','subline':'새로운 하루','cta':'살펴보기','palette':['#FFFFFF','#112233'],'rationale':'메시지를 줄였습니다.'}))
    result=providers.art_direction(configured,Brief(),'간결하게',httpx.MockTransport(handler))
    assert result['brief']['headline']=='더 명확하게'
    assert result['brief']['brand']=='MORNING'


def test_vision_contract_mock(configured):
    def handler(req):
        payload=json.loads(req.content)
        assert payload['input'][0]['content'][1]['image_url'].startswith('data:image/png;base64,')
        return httpx.Response(200,json=completed({'style_summary':'선명한 그래픽','objects':['원'],'visible_text':'','layout_hint':'orbit','uncertainties':['실제 의미는 확인할 수 없음']}))
    r=providers.describe_image(configured,b'test-image-placeholder',httpx.MockTransport(handler))
    assert r['method']=='openai-vision' and r['layout_hint']=='orbit'


def test_provider_failure_does_not_leak_body(configured):
    transport=httpx.MockTransport(lambda req:httpx.Response(401,text='secret-private-prompt'))
    with pytest.raises(providers.ProviderError) as e:providers.art_direction(configured,Brief(),'test',transport)
    assert 'secret-private-prompt' not in str(e.value)


def test_refusal_handled(configured):
    transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'status':'completed','output':[{'content':[{'type':'refusal','refusal':'No'}]}]}))
    with pytest.raises(providers.ProviderError):providers.art_direction(configured,Brief(),'test',transport)


def test_daily_call_cap(configured,monkeypatch):
    monkeypatch.setenv('MAX_PROVIDER_CALLS_PER_DAY','1')
    transport=httpx.MockTransport(lambda req:httpx.Response(429,text='rate limited'))
    with pytest.raises(providers.ProviderError):providers.art_direction(configured,Brief(),'test',transport)
    with pytest.raises(providers.ProviderError,match='호출 한도'):providers.art_direction(configured,Brief(),'test',transport)


def test_invalid_ai_colors_not_applied(configured):
    data={'headline':'ok','subline':'ok','cta':'ok','palette':['javascript:bad','#FFFFFF'],'rationale':'bad'}
    transport=httpx.MockTransport(lambda req:httpx.Response(200,json=completed(data)))
    with pytest.raises(providers.ProviderError):providers.art_direction(configured,Brief(),'test',transport)
