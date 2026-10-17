"""Offline tests for the planning aid, not tests for an implemented auto-runner."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('parallel_plan',ROOT/'scripts/parallel_plan.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
BASE=json.loads((ROOT/'docs/implementation/plan.json').read_text())

def ids(result):return {t['id'] for t in result['selected']}
def fresh():return copy.deepcopy(BASE)

def test_validate_real_plan():
    by=m.validate(BASE)
    assert len(by)==68 and sum(t['tier']=='core' for t in by.values())==65
    assert BASE['runtime_status']=='not_implemented_not_started'

def test_initial_only_bootstrap():assert ids(m.select_ready(BASE))=={'CL-001'}

def test_four_independent_after_baseline():
    assert ids(m.select_ready(BASE,{'CL-001'}))=={'CL-002','CL-007','CL-059','AUTO-001'}

def test_blocked_task_does_not_stop_unrelated():
    assert ids(m.select_ready(BASE,{'CL-001'},blocked={'CL-002'}))=={'CL-007','CL-059','AUTO-001'}

def test_running_is_not_redispatched_even_if_write_set_present():
    out=m.select_ready(BASE,{'CL-001'},running={'CL-002':['migrations/a.sql']},write_sets={'CL-002':['migrations/a.sql']})
    assert 'CL-002' not in ids(out) and len(out['selected'])<=3

def test_exact_paths_prevent_collisions():
    out=m.select_ready(BASE,{'CL-001'},write_sets={x:['shared/file.py'] for x in ['CL-002','CL-007','CL-059','AUTO-001']})
    assert len(out['selected'])==1

def test_resource_collision():
    p=fresh()
    for t in p['issues']:
        if t['id'] in {'CL-002','CL-007','CL-059','AUTO-001'}:t['resources']=['exclusive']
    assert len(m.select_ready(p,{'CL-001'})['selected'])==1

def test_early_start_requires_lock_and_never_means_merge_ready():
    done={'CL-001','AUTO-001'}
    # Suppress ordinary ready work to exercise only the allowed early UI preparation.
    blocked={i['id'] for i in BASE['issues']} - done - {'CL-006'}
    assert not m.select_ready(BASE,done,blocked=blocked)['selected']
    out=m.select_ready(BASE,done,blocked=blocked,contract_lock_verified=True)
    assert ids(out)=={'CL-006'} and out['selected'][0]['speculative']
    assert not out['selected'][0]['merge_dependency_ready']

def test_speculative_cap_one():
    done={'CL-001','AUTO-001','CL-003','CL-004'}
    allowed={'CL-006','CL-035','CL-036','CL-055'}
    blocked={t['id'] for t in BASE['issues']}-done-allowed
    out=m.select_ready(BASE,done,blocked=blocked,contract_lock_verified=True)
    assert len(out['selected'])==1

def test_gate_not_dispatched_as_coding_task():
    out=m.select_ready(BASE,{'CL-001','CL-002','CL-004'})
    assert 'CL-026' in out['external_candidates'] and 'CL-026' not in ids(out)

def test_reduced_dependencies_keep_live_gate():
    by=m.validate(BASE)
    assert m.dependencies(by['CL-018'])==['CL-017']
    assert m.dependencies(by['CL-044'])==['CL-019']
    assert m.dependencies(by['CL-028'])==['CL-027']
    assert by['CL-028']['live_requires']==['CL-026']
    assert 'CL-026' in m.dependencies(by['CL-034'])
    assert 'CL-061' in m.dependencies(by['CL-055'])
    assert 'CL-062' in m.dependencies(by['CL-055'])
    assert 'AUTO-006' in m.dependencies(by['CL-056'])

def test_no_extension_dispatched():
    done={t['id'] for t in BASE['issues'] if t['tier']=='core'}
    assert not m.select_ready(BASE,done,contract_lock_verified=True)['selected']

@pytest.mark.parametrize('case',['count','duplicate_id','duplicate_number','cycle','unknown','core_extension','resources','early_no_lock','live_unknown','weight','model','effort','slots','final_orphan'])
def test_invalid_plan_rejected(case):
    p=fresh(); by={t['id']:t for t in p['issues']}
    if case=='count':p['issue_count']=99
    elif case=='duplicate_id':p['issues'][1]['id']='CL-001'
    elif case=='duplicate_number':p['issues'][1]['issue_number']=8
    elif case=='cycle':by['CL-001']['depends_on']=['CL-002']
    elif case=='unknown':by['CL-001']['depends_on']=['MISSING']
    elif case=='core_extension':by['CL-002']['depends_on']=['CL-050']
    elif case=='resources':by['CL-001']['resources']=[]
    elif case=='early_no_lock':by['CL-006'].pop('contract_lock_required')
    elif case=='live_unknown':by['CL-028']['live_requires']=['CL-001']
    elif case=='weight':by['CL-001']['weight']=True
    elif case=='model':p['implementation_model']='other-model'
    elif case=='effort':p['reasoning_effort']='high'
    elif case=='slots':p['autonomy']['merger_slots']=2
    elif case=='final_orphan':by['CL-060']['depends_on'].remove('AUTO-005')
    with pytest.raises(ValueError):m.validate(p)

@pytest.mark.parametrize('bad',['../secrets','/tmp/file','x/../../y','C:/file','a\\b','a/*','.', ''])
def test_unsafe_paths_rejected(bad):
    with pytest.raises(ValueError):m.canonical_path(bad)

def test_prefix_paths():
    assert m.overlaps(['a/b'],['a/b/c'])
    assert m.overlaps(['a/b/c'],['a/b'])
    assert not m.overlaps(['a/b'],['a/b2'])

@pytest.mark.parametrize('kwargs',[{'slots':0},{'slots':7},{'slots':True},{'completed':{'MISSING'}},{'completed':{'CL-001'},'blocked':{'CL-001'}}])
def test_invalid_state_rejected(kwargs):
    with pytest.raises(ValueError):m.select_ready(BASE,**kwargs)

def test_cli_is_advisory_and_no_side_effects():
    proc=subprocess.run([sys.executable,'scripts/parallel_plan.py','--completed','CL-001'],cwd=ROOT,capture_output=True,text=True,check=True)
    out=json.loads(proc.stdout)
    assert out['mode']=='advisory_dry_run' and out['not_an_executor']
    assert out['completion_inputs_are_assumptions'] and len(out['selected'])==4
