import { render,screen,fireEvent } from '@testing-library/react';
import { describe,it,expect,vi } from 'vitest';
import { MathBlock,TestBanner,ScheduleMatrix,ErrorState,ResultMetrics,CostDistribution,Heatmap } from './components';
import { LambdaControl } from './pages/Laboratory';
import { BranchWalkthrough,FullFormulation,LinearRelaxationCalculus,MatrixFormulation,SearchSpaceNote,type BranchNode } from './pages/Education';
import { api,type Tx,type Result,type CostPoint } from './api';
import type { ReactNode } from 'react';

vi.mock('recharts',()=>({ResponsiveContainer:({children}:{children:ReactNode})=><div>{children}</div>,
 BarChart:({data,children}:{data:unknown;children:ReactNode})=><div data-testid="chart-data" data-values={JSON.stringify(data)}>{children}</div>,
 CartesianGrid:()=>null,XAxis:()=>null,YAxis:()=>null,Tooltip:()=>null,ReferenceLine:()=>null,Bar:()=>null,Cell:()=>null,
 LineChart:()=>null,Line:()=>null,Legend:()=>null,AreaChart:()=>null,Area:()=>null,ScatterChart:()=>null,Scatter:()=>null,ZAxis:()=>null}));
const tx=(id:string,release:number,deadline:number):Tx=>({transaction_id:id,gas_used:21000,release_slot:release,deadline_slot:deadline,priority_class:'URGENT',window_length:deadline-release+1,allowed_slots:[release,deadline],source_tx_hash:'0x'+'0'.repeat(64),source_block_time_utc:'2025-01-01'});
const workload=[tx('a',1,2),tx('b',3,4)];

describe('critical presentation contracts',()=>{
 it('renders mathematics with KaTeX without parse errors',()=>{const {container}=render(<MathBlock math={String.raw`\sum_{t=r_i}^{d_i}x_{it}=1`}/>);expect(container.querySelector('.katex')).toBeTruthy();expect(container.querySelector('.katex-error')).toBeNull();});
 it('changes lambda using the quick preset',()=>{const change=vi.fn();render(<LambdaControl value={0} onChange={change}/>);fireEvent.click(screen.getByRole('button',{name:/Light/}));expect(change).toHaveBeenCalledWith(.05);});
 it('labels TEST evaluation and fractional tail support',()=>{render(<TestBanner tail={4.5} exploratory/>);expect(screen.getByRole('note')).toHaveTextContent('EVALUATION ONLY');expect(screen.getByText(/4.50 scenario equivalents/)).toBeTruthy();expect(screen.getByText(/Exploratory what-if/)).toBeTruthy();});
 it('renders one assignment per transaction and unavailable slots',()=>{render(<ScheduleMatrix workload={workload} schedule={{a:2,b:3}} onSelect={()=>{}}/>);expect(screen.getAllByRole('button',{name:/ assigned$/})).toHaveLength(2);expect(screen.getByRole('button',{name:'b slot 1 unavailable'})).toBeTruthy();});
 it('comparison shows only changed rows and previous assignment',()=>{const inspect=vi.fn();render(<ScheduleMatrix workload={workload} schedule={{a:2,b:3}} other={{a:1,b:3}} changedOnly onSelect={inspect}/>);expect(screen.queryByRole('button',{name:/b slot/})).toBeNull();expect(screen.getByRole('button',{name:'a slot 1 previous'})).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'a slot 2 assigned'}));expect(inspect).toHaveBeenCalledWith(workload[0]);});
 it('shows errors rather than fabricated data',()=>{render(<ErrorState error={new Error('Live solve failed.')}/>);expect(screen.getByRole('alert')).toHaveTextContent('Live solve failed.');});
 it('renders returned optimization metrics with ETH precision',()=>{render(<ResultMetrics r={{alpha:.95,expected_cost_eth:.004407514,var_eth:.014,cvar_eth:.03415428,worst_case_cost_eth:.119} as Result}/>);expect(screen.getByText('0.004407514')).toBeTruthy();expect(screen.getByText('TRAIN CVaR 95.0%')).toBeTruthy();});
 it('passes backend CVaR points unchanged to visualization',()=>{const points=[{date:'2025-01-01',cost_eth:.01,eta_eth:.008,xi_eth:.002,probability:.1,rank:1,cumulative_probability:1,tail_mass:.05}] as CostPoint[];render(<CostDistribution points={points} varEth={.008} cvarEth={.01}/>);expect(JSON.parse(screen.getByTestId('chart-data').getAttribute('data-values')!)).toEqual(points);});
 it('heatmap supports keyboard day selection and complete rows',()=>{const change=vi.fn();render(<Heatmap data={{split:'TRAIN',dates:['2025-01-01','2025-01-02'],slots:[{slot:1,utc_range:'00:00–02:00 UTC'}],prices:[[1],[2]],unit:'gwei'}} selected="2025-01-01" onSelect={change}/>);fireEvent.change(screen.getByLabelText('Heatmap day'),{target:{value:'2025-01-02'}});expect(change).toHaveBeenCalledWith('2025-01-02');expect(screen.getByText(/entire row is one historical stochastic scenario/)).toBeTruthy();});
 it('API unavailable produces an actionable error',async()=>{vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error('offline')));await expect(api('health')).rejects.toThrow('Check that the GasOps backend or Docker services are running');vi.unstubAllGlobals();});
});

describe('Phase 3.1 mathematical deep dive',()=>{
 it('renders the complete objective and constraints',()=>{render(<FullFormulation/>);const model=screen.getByTestId('complete-model');const source=model.querySelector('annotation')?.textContent??'';expect(model).toHaveTextContent('COMPLETE FORMULATION');expect(source).toContain('\\min_{x,\\eta,\\xi}');expect(source).toContain('\\sum_{t:(i,t)\\in\\mathcal A}x_{it}=1');expect(source).toContain('\\xi_s\\ge C_s(x)-\\eta');expect(source).toContain('x_{it}\\in\\{0,1\\}');expect(model.querySelector('.katex-error')).toBeNull();expect(screen.getByRole('button',{name:/Copy model/})).toBeTruthy();});
 it('uses runtime empirical dimensions in the matrix formulation',()=>{render(<MatrixFormulation transactions={30} scenarios={365} binaries={140} variables={506} constraints={395}/>);const matrix=screen.getByTestId('matrix-formulation');expect(matrix).toHaveTextContent('365 × 140');expect(matrix).toHaveTextContent('30 × 140');expect(matrix).toHaveTextContent('506 variables / 395 constraints');expect(matrix).toHaveTextContent('Ax = 1');});
 it('states the constant gradient and zero Hessian only for the relaxation',()=>{render(<LinearRelaxationCalculus/>);const section=screen.getByTestId('linear-calculus');expect(section).toHaveTextContent('Constant everywhere in the continuous relaxation');expect(section).toHaveTextContent('zero matrix');expect(section).toHaveTextContent('Newton or Hessian methods therefore do not solve the integer problem');expect(section).not.toHaveTextContent('Newton solves the MILP');});
 const nodes:BranchNode[]=[
  {id:'root',parent:null,fixed:{},bound:3.5,x:.5,y:1,status:'fractional relaxation',reason:'branch'},
  {id:'x0',parent:'root',fixed:{x:0},bound:null,x:null,y:null,status:'infeasible',reason:'prune'},
  {id:'x1',parent:'root',fixed:{x:1},bound:4,x:1,y:.5,status:'fractional relaxation',reason:'branch'},
  {id:'y0',parent:'x1',fixed:{x:1,y:0},bound:null,x:null,y:null,status:'infeasible',reason:'prune'},
  {id:'y1',parent:'x1',fixed:{x:1,y:1},bound:5,x:1,y:1,status:'integer incumbent',reason:'incumbent'},
 ];
 it('shows every hand-calculated branch-and-bound result',()=>{const {rerender}=render(<BranchWalkthrough nodes={nodes} depth={2} selected="root" onSelect={()=>{}}/>);expect(screen.getByText('LB = 3.5')).toBeTruthy();rerender(<BranchWalkthrough nodes={nodes} depth={2} selected="x0" onSelect={()=>{}}/>);expect(screen.getByText('Prune by infeasibility')).toBeTruthy();rerender(<BranchWalkthrough nodes={nodes} depth={2} selected="x1" onSelect={()=>{}}/>);expect(screen.getByText('LB = 4.0')).toBeTruthy();rerender(<BranchWalkthrough nodes={nodes} depth={2} selected="y1" onSelect={()=>{}}/>);expect(screen.getByText('UB = 5')).toBeTruthy();expect(screen.getByText('Integer feasible: update incumbent')).toBeTruthy();});
 it('describes 2^140 as unconstrained vectors rather than feasible schedules',()=>{render(<SearchSpaceNote binaries={140}/>);const note=screen.getByTestId('search-space');expect(note).toHaveTextContent('UNCONSTRAINED BINARY SEARCH SPACE');expect(note).toHaveTextContent('1.39 × 10^42');expect(note).toHaveTextContent('not feasible schedules');});
});
