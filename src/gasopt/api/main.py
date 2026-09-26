"""Versioned local API. Start with uvicorn gasopt.api.main:app --reload."""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from gasopt.api.study import Study
from gasopt.api.schemas import (SolveRequest, SolveResponse, ScheduleRequest, ComparisonRequest,
                               ScenarioRequest, CalculatorRequest, EvaluationResponse)
from gasopt.api.serialization import records
from gasopt.api.education import branch_demo

def create_app(root: Path | None = None, study: Study | None = None):
    root = root or Path(os.environ.get('GASOPS_ROOT', Path(__file__).resolve().parents[3]))
    @asynccontextmanager
    async def lifespan(app):
        try:
            app.state.study = study or Study(root)
            app.state.load_error = None
        except (OSError, ValueError, KeyError) as exc:
            logging.exception('GasOps local study could not be loaded')
            app.state.study = None
            app.state.load_error = f'Local study unavailable: {exc}'
        yield
    app = FastAPI(title='GasOps', version='1.0.0', lifespan=lifespan)
    if os.environ.get('GASOPS_DEV') == '1':
        app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],
                           allow_methods=['GET','POST'], allow_headers=['Content-Type'])
    def snapshot(request):
        if request.app.state.study is None:
            raise HTTPException(503, request.app.state.load_error)
        return request.app.state.study
    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse(status_code=422, content={'detail': str(exc)})
    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={'detail': str(exc)})
    @app.get('/api/v1/health')
    def health(request: Request):
        s = snapshot(request)
        return {'status':'ok','product':'GasOps','dataset_id':s.dataset_id,'offline':True}
    @app.get('/api/v1/study/meta')
    def meta(request: Request): return snapshot(request).meta()
    @app.get('/api/v1/study/results')
    def results(request: Request): return records(snapshot(request).test_table)
    @app.get('/api/v1/study/sensitivity')
    def sensitivity(request: Request): return snapshot(request).sensitivity()
    @app.get('/api/v1/study/archive/{strategy}', response_model=SolveResponse)
    def archive(strategy: str, request: Request): return snapshot(request).archive(strategy)
    @app.get('/api/v1/data/slot-profile')
    def profile(request: Request): return snapshot(request).profile()
    @app.get('/api/v1/data/gas-history')
    def history(request: Request, split: Literal['TRAIN','TEST','ALL']='TRAIN'):
        return records(snapshot(request).frames[split][['day','slot','slot_start_utc','median_gas_price_gwei']])
    @app.get('/api/v1/data/heatmap')
    def heatmap(request: Request, split: Literal['TRAIN','TEST']='TRAIN'): return snapshot(request).heatmap(split)
    @app.get('/api/v1/data/gas-used')
    def gas_used(request: Request): return snapshot(request).gas_used()
    @app.get('/api/v1/workload')
    def workload(request: Request): return snapshot(request).workload_rows()
    @app.get('/api/v1/model/summary')
    def model(request: Request):
        s=snapshot(request)
        return {'transactions':len(s.transactions),'train_scenarios':len(s.train),'slots':len(s.train[0].prices_gwei),
                'mean_prices_gwei':s.means,'here_and_now':True,'gwei_to_eth':1e-9,'capacity_constraints':False}
    @app.get('/api/v1/model/diagnostics')
    def diagnostics(request: Request):
        return records(snapshot(request).train_table.drop(columns=['schedule']))
    @app.post('/api/v1/optimization/solve', response_model=SolveResponse)
    def solve(body: SolveRequest, request: Request):
        try: return snapshot(request).solve(body.lambda_risk, body.alpha)
        except RuntimeError as exc:
            logging.exception('Live solve failed')
            raise HTTPException(503, 'Live solve failed. '+str(exc)+'. Archived Phase 2 results remain available explicitly.') from exc
    @app.post('/api/v1/evaluation/frozen-schedule', response_model=EvaluationResponse)
    def evaluation(body: ScheduleRequest, request: Request): return snapshot(request).evaluate(body.schedule,body.alpha)
    @app.get('/api/v1/evaluation/daily-costs')
    def daily(request: Request): return records(snapshot(request).daily_test)
    @app.post('/api/v1/analysis/compare')
    def compare(body: ComparisonRequest, request: Request): return snapshot(request).compare(body.schedule_a,body.schedule_b,body.alpha)
    @app.post('/api/v1/analysis/scenario')
    def scenario(body: ScenarioRequest, request: Request):
        return snapshot(request).scenario(body.schedule,body.split,body.day,body.selector,body.alpha)
    @app.post('/api/v1/analysis/calculator')
    def calculator(body: CalculatorRequest, request: Request):
        return snapshot(request).calculator(body.transaction_id,body.day,body.slot)
    @app.get('/api/v1/education/branch-and-bound')
    def education(request: Request):
        snapshot(request)
        return branch_demo()
    return app

app = create_app()
