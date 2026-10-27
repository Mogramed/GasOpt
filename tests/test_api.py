"""GasOps contract/integrity tests against the local archived empirical study."""
from copy import deepcopy
from pathlib import Path
import pytest
import numpy as np
from fastapi.testclient import TestClient
from gasopt.api.main import create_app
from gasopt.api.study import Study
from gasopt.api.schemas import SolveResponse, EvaluationResponse
from gasopt.api.optimization import TrainingOptimizer
from gasopt.evaluation.metrics import weighted_var_cvar, scenario_costs_eth
from gasopt.types import Scenario

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def study():
    if not (ROOT/'data/processed/metadata.json').exists():
        pytest.skip('Empirical integration tests require the archived Phase 2 data bundle.')
    return Study(ROOT)

@pytest.fixture(scope='module')
def client(study):
    with TestClient(create_app(study=study)) as c:
        yield c

@pytest.mark.parametrize('path', ['health','study/meta','study/results','study/sensitivity',
    'workload','data/slot-profile','data/gas-history','data/heatmap','data/gas-used',
    'model/summary','model/diagnostics','evaluation/daily-costs'])
def test_read_contracts(client,path):
    r=client.get('/api/v1/'+path)
    assert r.status_code==200 and r.json()

def test_dataset_dimensions(client):
    m=client.get('/api/v1/study/meta').json()
    assert (m['train_days'],m['test_days'],m['transaction_count'],m['slots'])==(365,90,30,12)
    assert len(client.get('/api/v1/workload').json())==30
    assert len(client.get('/api/v1/data/slot-profile').json())==12
    assert len(client.get('/api/v1/study/sensitivity').json())==11

@pytest.mark.parametrize('payload',[{'lambda_risk':-1},{'alpha':0},{'alpha':1},
    {'alpha':.999},{'lambda_risk':True},{'lambda_risk':'NaN'},{'alpha':False},{'unexpected':1}])
def test_invalid_parameters(client,payload):
    assert client.post('/api/v1/optimization/solve',json=payload).status_code==422

@pytest.mark.parametrize('risk',[0,.05,.1,.25,.5,.75,1,1.5,2,3,5])
def test_live_regression_all_prespecified_weights(client,study,risk):
    r=client.post('/api/v1/optimization/solve',json={'lambda_risk':risk,'alpha':.95})
    assert r.status_code==200,r.text
    live=SolveResponse.model_validate(r.json())
    archived=study.archive(f'cvar_lambda_{risk:g}')
    assert live.schedule==archived['schedule']
    assert live.expected_cost_eth==pytest.approx(archived['expected_cost_eth'],abs=1e-12)
    assert live.cvar_eth==pytest.approx(archived['cvar_eth'],abs=1e-12)
    assert live.solver_status=='optimal' and live.num_binary_variables==140
    costs=[p.cost_eth for p in live.scenario_costs]
    var,cvar=weighted_var_cvar(costs,[1/len(costs)]*len(costs),.95)
    assert live.var_eth==var and live.cvar_eth==pytest.approx(cvar)
    assert sum(p.tail_mass for p in live.scenario_costs)==pytest.approx(.05)
    for tx in study.transactions:
        assert tx.release_slot<=live.schedule[tx.id]<=tx.deadline


def test_live_calculation_trace_is_numerically_complete(client, study):
    response = client.post('/api/v1/optimization/solve', json={
        'lambda_risk': .05, 'alpha': .95, 'force_recompute': True})
    assert response.status_code == 200, response.text
    live = SolveResponse.model_validate(response.json())
    trace = live.calculation_trace
    assert live.origin == 'live'
    assert trace.inputs['transactions'] == 30
    assert trace.inputs['train_scenarios'] == 365
    assert trace.inputs['slots'] == 12
    assert trace.model == {
        'binary_variables': 140, 'continuous_variables': 366,
        'total_variables': 506, 'assignment_constraints': 30,
        'excess_constraints': 365, 'total_constraints': 395}
    weighted_excess = sum(point.probability * point.xi_eth for point in live.scenario_costs)
    assert trace.risk['weighted_excess_eth'] == pytest.approx(weighted_excess, abs=1e-12)
    assert trace.risk['cvar_eth'] == pytest.approx(
        trace.risk['eta_eth'] + weighted_excess / (1 - live.alpha), abs=1e-12)
    assert trace.objective['risk_penalty_eth'] == pytest.approx(.05 * live.cvar_eth)
    assert trace.objective['objective_value_eth'] == pytest.approx(
        live.expected_cost_eth + .05 * live.cvar_eth, abs=1e-12)
    example = trace.coefficient_example
    assert example['coefficient_eth'] == pytest.approx(
        example['gas_used'] * example['gas_price_gwei'] * 1e-9, abs=1e-12)
    assert trace.solver['node_count'] == live.node_count
    assert live.node_count is not None
    assert trace.solver['objective_bound_eth'] == pytest.approx(live.objective_value_eth)
    assert trace.solution['assignment_count'] == 30


def test_lambda_zero_trace_marks_cvar_as_post_solve(client):
    live = SolveResponse.model_validate(client.post('/api/v1/optimization/solve', json={
        'lambda_risk': 0.0, 'alpha': .95, 'force_recompute': True}).json())
    assert live.calculation_trace.risk['in_objective'] is False
    assert live.calculation_trace.model['continuous_variables'] == 0
    assert live.calculation_trace.objective['risk_penalty_eth'] == 0


def test_transaction_decision_trace_recomputes_real_counterfactuals(client, study):
    live = client.post('/api/v1/optimization/solve', json={
        'lambda_risk': .05, 'alpha': .95, 'force_recompute': True}).json()
    tx = next(item for item in study.transactions if item.deadline > item.release_slot)
    original = live['schedule'].copy()
    response = client.post('/api/v1/analysis/decision-trace', json={
        'schedule': original, 'transaction_id': tx.id,
        'lambda_risk': .05, 'alpha': .95})
    assert response.status_code == 200, response.text
    trace = response.json()
    assert live['schedule'] == original
    assert trace['transaction']['transaction_id'] == tx.id
    assert trace['transaction']['selected_slot'] == original[tx.id]
    assert len(trace['slot_outputs']) == tx.deadline - tx.release_slot + 1
    assert len(trace['scenario_outputs']) == 365
    selected = trace['selected_output']
    assert selected['portfolio_expected_cost_eth'] == pytest.approx(live['expected_cost_eth'])
    assert selected['portfolio_cvar_eth'] == pytest.approx(live['cvar_eth'])
    assert selected['portfolio_objective_eth'] == pytest.approx(live['objective_value_eth'])
    assert trace['optimality_check']['selected_is_best_one_move'] is True
    for row in trace['slot_outputs']:
        assert row['transaction_expected_cost_eth'] == pytest.approx(
            1e-9 * tx.gas_used * study.means[row['slot'] - 1])
        assert row['portfolio_objective_eth'] == pytest.approx(
            row['portfolio_expected_cost_eth'] + .05 * row['portfolio_cvar_eth'])
        assert row['delta_objective_eth'] == pytest.approx(
            row['portfolio_objective_eth'] - selected['portfolio_objective_eth'])


def test_transaction_decision_trace_rejects_unknown_transaction(client, study):
    response = client.post('/api/v1/analysis/decision-trace', json={
        'schedule': study.schedules['mean_price'], 'transaction_id': 'missing',
        'lambda_risk': 0.0, 'alpha': .95})
    assert response.status_code == 422

def test_train_only_even_if_test_prices_change(client,study,monkeypatch):
    import gasopt.api.optimization as module
    original=module.solve_stochastic
    seen=[]
    def spy(transactions,scenarios,config):
        seen.extend(s.id for s in scenarios)
        return original(transactions,scenarios,config)
    monkeypatch.setattr(module,'solve_stochastic',spy)
    monkeypatch.setattr(study,'test',tuple(Scenario(s.id,tuple(p*1000 for p in s.prices_gwei),s.probability) for s in study.test))
    first=client.post('/api/v1/optimization/solve',json={'lambda_risk':.123}).json()
    assert seen and max(seen)<study.config.test_start.isoformat()
    fresh=TrainingOptimizer(study.transactions,study.train,study.config,'independent')
    second,_,_=fresh.solve(.123,.95)
    assert first['schedule']==second.schedule
    assert first['expected_cost_eth']==second.expected_cost_eth

def test_evaluation_is_frozen_no_solve_and_matches_archive(client,study,monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('Evaluation attempted optimization')
    monkeypatch.setattr(study.optimizer,'solve',forbidden)
    schedule=deepcopy(study.schedules['cvar_lambda_0.05']); before=deepcopy(schedule)
    r=client.post('/api/v1/evaluation/frozen-schedule',json={'schedule':schedule})
    e=EvaluationResponse.model_validate(r.json())
    assert e.schedule==before==schedule
    saved=study.test_table.set_index('strategy').loc['cvar_lambda_0.05']
    for k,v in e.metrics.items(): assert v==pytest.approx(saved[k],abs=1e-12)
    assert '4.50' in e.warning

@pytest.mark.parametrize('defect',['missing','extra','early','late','float','bool'])
def test_invalid_schedule(client,study,defect):
    s=study.schedules['mean_price'].copy()
    if defect=='missing': s.pop('treasury_01')
    elif defect=='extra': s['fake']=1
    else: s['treasury_01']={'early':0,'late':12,'float':1.5,'bool':True}[defect]
    assert client.post('/api/v1/evaluation/frozen-schedule',json={'schedule':s}).status_code==422

def test_comparison_calculator_equivalence(client,study):
    a,b=study.schedules['mean_price'],study.schedules['cvar_lambda_0.05']
    r=client.post('/api/v1/analysis/compare',json={'schedule_a':a,'schedule_b':b}).json()
    assert r['changed_count']==11
    tx=study.transactions[0]; s=study.train[0]; slot=tx.release_slot
    c=client.post('/api/v1/analysis/calculator',json={'transaction_id':tx.id,'day':s.id,'slot':slot}).json()
    assert c['cost_eth']==pytest.approx(tx.gas_used*s.prices_gwei[slot-1]*1e-9)
    m=study.train_table.set_index('strategy')
    assert m.loc['mean_price','objective_value_eth']==pytest.approx(m.loc['expected_value_equivalence','objective_value_eth'])

def test_cache_error_fallback_and_missing_data(client,study,monkeypatch,tmp_path):
    a=client.post('/api/v1/optimization/solve',json={'lambda_risk':.05}).json()
    b=client.post('/api/v1/optimization/solve',json={'lambda_risk':.05}).json()
    assert b['origin']=='cached_live' and b['schedule']==a['schedule']
    c=client.post('/api/v1/optimization/solve',json={
        'lambda_risk':.05, 'force_recompute':True}).json()
    assert c['origin']=='live' and c['schedule']==a['schedule']
    def failed(*args,**kwargs): raise RuntimeError('infeasible test injection')
    monkeypatch.setattr(study.optimizer,'solve',failed)
    r=client.post('/api/v1/optimization/solve',json={})
    assert r.status_code==503 and 'Live solve failed' in r.json()['detail']
    assert client.get('/api/v1/study/archive/mean_price').json()['origin']=='archived'
    with TestClient(create_app(root=tmp_path)) as missing:
        assert missing.get('/api/v1/health').status_code==503
        assert missing.get('/api/v1/workload').status_code==503
