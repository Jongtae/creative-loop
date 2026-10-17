"""Offline plan validator and advisory selector; never spawns, pays, pushes or merges.

--completed is an ASSUMPTION for planning, not verified completion evidence.
AUTO-002 must verify durable evidence/leases before any real dispatch.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any


def dependencies(task: dict[str, Any], stage: str = 'merge') -> list[str]:
    if stage == 'merge':
        return task.get('merge_requires', task['depends_on'])
    if stage == 'start':
        return task.get('start_requires', task['depends_on'])
    raise ValueError('Unknown dependency stage')


def validate(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if plan.get('schema_version') != 2:
        raise ValueError('schema_version must be 2')
    tasks = plan.get('issues', [])
    if not tasks or plan.get('issue_count') != len(tasks):
        raise ValueError('issue_count mismatch')
    by = {t['id']: t for t in tasks}
    if len(by) != len(tasks) or len({t['issue_number'] for t in tasks}) != len(tasks):
        raise ValueError('Duplicate task ID or GitHub issue number')
    if plan.get('implementation_model') != 'gpt-5.6-terra' or plan.get('reasoning_effort') != 'medium':
        raise ValueError('Model or effort drift')
    for ident, task in by.items():
        if task.get('tier') not in {'core', 'extension'} or task.get('kind') not in {'implementation', 'gate'}:
            raise ValueError('Invalid tier/kind')
        resources = task.get('resources')
        if not resources or not all(isinstance(x, str) and x for x in resources) or len(set(resources)) != len(resources):
            raise ValueError('Missing/duplicate resources')
        if not task.get('lane') or not task.get('mvp_ids'):
            raise ValueError('Missing lane or acceptance mapping')
        for stage in ('start', 'merge'):
            deps = dependencies(task, stage)
            if not isinstance(deps, list) or len(set(deps)) != len(deps):
                raise ValueError('Invalid/duplicate dependencies')
            for dep in deps:
                if dep not in by or dep == ident:
                    raise ValueError(f'Unknown/self dependency: {ident} {dep}')
                if task['tier'] == 'core' and by[dep]['tier'] == 'extension':
                    raise ValueError('Core cannot depend on extension')
            if stage == 'start' and set(deps) != set(dependencies(task)) and not task.get('contract_lock_required'):
                raise ValueError('Early start requires a frozen contract')
        for gate in task.get('live_requires', []):
            if gate.startswith('owner:'):
                continue
            if gate not in by or by[gate]['kind'] != 'gate':
                raise ValueError('Unknown live gate')
        weight = task.get('weight', 1)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 < weight < 1000000:
            raise ValueError('Invalid planning weight')
    # Check each DAG AND the union: no hidden contract/merge circular dependency.
    for stage in ('start', 'merge', 'union'):
        visiting: set[str] = set(); done: set[str] = set()
        def visit(ident: str) -> None:
            if ident in visiting:
                raise ValueError(f'Cycle in {stage}: {ident}')
            if ident in done:
                return
            visiting.add(ident)
            ds = (set(dependencies(by[ident], 'start')) | set(dependencies(by[ident]))) if stage == 'union' else dependencies(by[ident], stage)
            for dep in ds:
                visit(dep)
            visiting.remove(ident); done.add(ident)
        for ident in by:
            visit(ident)
    pool = plan.get('autonomy', {})
    if (pool.get('builder_slots') != 4 or pool.get('reviewer_slots') != 2 or
        pool.get('merger_slots') != 1 or pool.get('max_speculative_slots') != 1 or
        pool.get('max_builder_slots') != 6 or pool.get('live_product_calls_default') != 0):
        raise ValueError('Unexpected pool/safety policy')
    # All mandatory work must be on the final acceptance ancestor graph.
    ancestors: set[str] = set()
    def collect(ident: str) -> None:
        for dep in dependencies(by[ident]):
            if dep not in ancestors:
                ancestors.add(dep); collect(dep)
    if 'CL-060' not in by:
        raise ValueError('Missing final acceptance')
    collect('CL-060')
    missing = {i for i,t in by.items() if t['tier']=='core' and i!='CL-060'} - ancestors
    if missing:
        raise ValueError(f'Core work not required by final acceptance: {sorted(missing)}')
    return by


def canonical_path(value: str) -> str:
    if not value or '\\' in value or any(c in value for c in '*?[]'):
        raise ValueError('Write paths must be exact relative paths, no globs')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or ':' in value or str(p) == '.':
        raise ValueError('Unsafe write path')
    return str(p).rstrip('/')


def overlaps(left: list[str], right: list[str]) -> bool:
    a = [canonical_path(p) for p in left]; b = [canonical_path(p) for p in right]
    return any(x == y or x.startswith(y + '/') or y.startswith(x + '/') for x in a for y in b)


def critical_scores(by: dict[str, dict[str, Any]]) -> dict[str, int]:
    children = {i: [] for i in by}
    for i,t in by.items():
        for dep in dependencies(t):
            children[dep].append(i)
    memo: dict[str, int] = {}
    def length(i: str) -> int:
        if i not in memo:
            memo[i] = 1 + max((length(c) for c in children[i]), default=0)
        return memo[i]
    return {i: length(i) for i in by}


def select_ready(plan: dict[str, Any], completed: set[str] | None = None,
                 running: dict[str, list[str]] | None = None,
                 blocked: set[str] | None = None, slots: int = 4,
                 contract_lock_verified: bool = False,
                 write_sets: dict[str, list[str]] | None = None) -> dict[str, Any]:
    by = validate(plan)
    completed = set(completed or ()); running = dict(running or {}); blocked = set(blocked or ())
    write_sets = dict(write_sets or {})
    all_state = completed | set(running) | blocked | set(write_sets)
    if all_state - by.keys():
        raise ValueError('State refers to unknown tasks')
    if completed & (set(running) | blocked) or set(running) & blocked:
        raise ValueError('Contradictory task state')
    if not isinstance(slots, int) or isinstance(slots, bool) or not 1 <= slots <= 6 or len(running)>slots:
        raise ValueError('Invalid builder slots')
    for paths in [*running.values(), *write_sets.values()]:
        for path in paths: canonical_path(path)
    score = critical_scores(by)
    claimed = {r for i in running for r in by[i]['resources']}
    claimed_paths = [p for ps in running.values() for p in ps]
    speculative = sum(not set(dependencies(by[i])) <= completed for i in running)
    selected = []; external = []
    candidates = [i for i,t in by.items() if t['tier']=='core' and i not in (completed | set(running) | blocked)
                  and set(dependencies(t, 'start')) <= completed]
    candidates.sort(key=lambda i: (not set(dependencies(by[i])) <= completed, -score[i], i))
    for i in candidates:
        t = by[i]
        if t['kind']=='gate':
            external.append(i); continue
        if len(selected)+len(running) >= slots:
            continue
        is_speculative = not set(dependencies(t)) <= completed
        if is_speculative and (not contract_lock_verified or speculative >= 1):
            continue
        if t.get('contract_lock_required') and not contract_lock_verified:
            continue
        if claimed & set(t['resources']) or overlaps(claimed_paths, write_sets.get(i, [])):
            continue
        selected.append({'id':i, 'issue_number':t['issue_number'], 'speculative':is_speculative,
                         'merge_dependency_ready':not is_speculative,
                         'write_manifest_verified':False})
        speculative += int(is_speculative); claimed.update(t['resources']); claimed_paths += write_sets.get(i, [])
    return {'mode':'advisory_dry_run', 'not_an_executor':True,
            'completion_inputs_are_assumptions':True, 'selected':selected,
            'external_candidates':external, 'blocked':sorted(blocked),
            'note':'No process, API, GitHub write, lease or completion evidence is created.'}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=Path('docs/implementation/plan.json'))
    parser.add_argument('--completed',nargs='*',default=[])
    parser.add_argument('--slots',type=int,default=4)
    parser.add_argument('--assume-contract-lock',action='store_true')
    args=parser.parse_args()
    try:
        p=json.loads(args.plan.read_text(encoding='utf-8')); by=validate(p)
        result=select_ready(p,set(args.completed),slots=args.slots,contract_lock_verified=args.assume_contract_lock)
        result.update(tasks=len(by),core=sum(t['tier']=='core' for t in by.values()),extension=sum(t['tier']=='extension' for t in by.values()))
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))

if __name__=='__main__': main()
