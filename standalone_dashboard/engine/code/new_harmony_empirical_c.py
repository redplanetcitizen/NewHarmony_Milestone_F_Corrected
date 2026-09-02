from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import csv, json
import numpy as np

HARMONY_OFFSET=1.1
DEFAULT_EPSILON=0.25/14.0  # retained to isolate M05-M07
DEFAULT_MIN_CV=0.034


def harmony(x):
    x=np.asarray(x,dtype=float)
    return x/(HARMONY_OFFSET+x)

def harmony_inverse(h):
    h=np.asarray(h,dtype=float)
    return HARMONY_OFFSET*h/(1.0-h)

def read_matrix(path:Path,sectors:list[str]):
    rows=list(csv.reader(open(path,encoding='utf-8-sig',newline='')))
    hdr=[x.strip() for x in rows[0][1:]]; rowcodes=[r[0].strip() for r in rows[1:]]
    raw=np.array([[float(x) for x in r[1:]] for r in rows[1:]],float)
    rid={c:i for i,c in enumerate(rowcodes)}; cid={c:i for i,c in enumerate(hdr)}
    return raw[np.ix_([rid[c] for c in sectors],[cid[c] for c in sectors])]

def read_vector(path:Path,sectors:list[str]):
    rr=list(csv.DictReader(open(path,encoding='utf-8-sig')))
    value_col=[k for k in rr[0].keys() if k not in ('bea_code','sector_name')][0]
    d={r['bea_code']:float(r[value_col]) for r in rr}
    return np.array([d[c] for c in sectors],float)

@dataclass
class ModelData:
    years:list[int]
    sectors:list[str]
    names:dict[str,str]
    A_by_year:np.ndarray
    L_by_year:np.ndarray
    C:np.ndarray
    dep_by_year:np.ndarray
    initial_stock:np.ndarray
    goals:np.ndarray
    labour_coeff_by_year:np.ndarray
    labour_available:np.ndarray
    observed_gross:dict[int,np.ndarray]
    observed_stock:dict[int,np.ndarray]
    observed_investment:dict[int,np.ndarray]
    mode:str

@dataclass
class Scenario:
    investments:np.ndarray
    stock_start:np.ndarray
    stock_end:np.ndarray
    gross_required:np.ndarray
    gross_realized:np.ndarray
    total_final_required:np.ndarray
    net_social_output:np.ndarray
    fulfillment:np.ndarray
    annual_harmony:np.ndarray
    mean_harmony:float
    std_harmony:float
    cv_harmony:float
    capital_constraint:np.ndarray
    labour_constraint:np.ndarray
    feasible_ratio:np.ndarray

@dataclass
class SolveResult:
    initial:Scenario
    final:Scenario
    transfers:list[dict]
    stop_reason:str
    iterations:int


def _sector_list(data_dir:Path):
    # Capital matrix carries the canonical 71 sector order.
    rows=list(csv.reader(open(data_dir/'capital_stock_matrix_real_2018.csv',encoding='utf-8-sig',newline='')))
    sectors=[r[0].strip() for r in rows[1:]]
    names={c:c for c in sectors}
    # names are optional for solver; populate from any vector CSV.
    rr=list(csv.DictReader(open(data_dir/'gross_output_real_2019.csv',encoding='utf-8-sig')))
    names.update({r['bea_code']:r['sector_name'] for r in rr})
    return sectors,names


def load_model_data(data_dir:Path, mode:str='frozen')->ModelData:
    mode=mode.lower()
    if mode not in ('frozen','historical'):
        raise ValueError('mode must be frozen or historical')
    sectors,names=_sector_list(data_dir); years=[2019,2020,2021,2022,2023]
    N=len(sectors); T=len(years)

    A_hist=np.array([read_matrix(data_dir/f'A_real_{y}.csv',sectors) for y in years])
    if mode=='frozen':
        A=np.repeat(A_hist[0][None,:,:],T,axis=0)
    else:
        A=A_hist.copy()
    L=np.array([np.linalg.inv(np.eye(N)-A[t]) for t in range(T)])
    C=read_matrix(data_dir/'capital_coefficients_C_real_2018_2019.csv',sectors)
    dep=np.array([read_matrix(data_dir/f'depreciation_rate_matrix_{y}.csv',sectors) for y in years])
    S0=read_matrix(data_dir/'capital_stock_matrix_real_2018.csv',sectors)

    # goals + labour resources
    rows=list(csv.reader(open(data_dir/'plan_targets_real_2019_2023.csv',encoding='utf-8-sig',newline='')))
    hdr=rows[0]; codecols=hdr[1:-1]; order=[codecols.index(c) for c in sectors]
    goals=[]; lav=[]
    for r in rows[1:]:
        vals=np.array([float(x) for x in r[1:-1]],float)
        goals.append(vals[order]); lav.append(float(r[-1]))
    labour_coeff=np.array([read_vector(data_dir/f'labour_coeff_fte_{y}.csv',sectors) for y in years])
    og={y:read_vector(data_dir/f'gross_output_real_{y}.csv',sectors) for y in years}
    os={2018:read_vector(data_dir/'capital_stock_real_2018.csv',sectors)}
    os.update({y:read_vector(data_dir/f'capital_stock_real_{y}.csv',sectors) for y in years})
    oi={y:read_vector(data_dir/f'investment_real_{y}.csv',sectors) for y in years}
    return ModelData(years,sectors,names,A,L,C,dep,S0,np.array(goals),labour_coeff,np.array(lav),og,os,oi,mode)


def evaluate(data:ModelData, investments:np.ndarray)->Scenario:
    """Evaluate one scenario, preserving M01-M04 and adding M05-M07.

    Investment is a committed prior claim in each source year.  The social plan ray is
    scaled by the largest scalar compatible with capital and physical FTE labour.  The
    annual technology matrix A_t and Leontief inverse L_t are selected by the benchmark
    mode.  Investment produced in t enters productive stock at end-t/start-(t+1).
    """
    T,N=data.goals.shape
    stock_start=np.zeros((T,N,N)); stock_end=np.zeros_like(stock_start)
    gross_req=np.zeros((T,N)); gross_real=np.zeros_like(gross_req)
    total_final=np.zeros_like(gross_req); net_social=np.zeros_like(gross_req)
    fulfillment=np.full_like(gross_req,np.nan)
    hc=np.zeros(T); lc=np.zeros(T); fr=np.zeros(T); ah=np.zeros(T)
    stock_start[0]=data.initial_stock
    for t in range(T):
        if t>0: stock_start[t]=stock_end[t-1]
        L=data.L_by_year[t]
        inv_by_source=investments[t].sum(axis=1)
        total_final[t]=data.goals[t]+inv_by_source
        gross_social=L@data.goals[t]
        gross_inv=L@inv_by_source
        gross_req[t]=gross_social+gross_inv

        cap_limit=np.full(N,np.inf)
        for j in range(N):
            mask=data.C[:,j]>1e-12
            if np.any(mask): cap_limit[j]=float(np.min(stock_start[t,mask,j]/data.C[mask,j]))

        cap_bounds=[]; investment_capital_feasible=True
        for j in range(N):
            if gross_inv[j]>cap_limit[j]+1e-8: investment_capital_feasible=False
            if gross_social[j]>1e-12: cap_bounds.append((cap_limit[j]-gross_inv[j])/gross_social[j])
        hc[t]=float(min(cap_bounds)) if cap_bounds else np.inf

        lcoef=data.labour_coeff_by_year[t]
        lab_social=float(lcoef@gross_social); lab_inv=float(lcoef@gross_inv)
        lc[t]=float((data.labour_available[t]-lab_inv)/lab_social) if lab_social>1e-12 else np.inf
        raw_f=min(hc[t],lc[t])
        if not investment_capital_feasible: raw_f=min(raw_f,-1.0)
        fr[t]=raw_f; f=max(0.0,raw_f)
        gross_real[t]=gross_inv+f*gross_social
        net_social[t]=f*data.goals[t]
        mask=data.goals[t]>1e-12; fulfillment[t,mask]=f
        ah[t]=float(harmony(f))
        stock_end[t]=stock_start[t]*(1.0-data.dep_by_year[t])+investments[t]
    mean=float(np.mean(ah)); std=float(np.std(ah,ddof=1)); cv=std/abs(mean) if mean!=0 else np.inf
    return Scenario(investments.copy(),stock_start,stock_end,gross_req,gross_real,total_final,net_social,fulfillment,ah,mean,std,cv,hc,lc,fr)


def capital_gap_for_harmony_step(data:ModelData,scenario:Scenario,dest:int,epsilon:float):
    target_f=float(harmony_inverse(scenario.mean_harmony))
    current_f=float(harmony_inverse(scenario.annual_harmony[dest]))
    diff=max(0.0,target_f-current_f); step=diff*epsilon; desired=current_f+step
    inv_by_source=scenario.investments[dest].sum(axis=1)
    desired_final=data.goals[dest]*desired+inv_by_source
    gross_desired=data.L_by_year[dest]@desired_final
    required=data.C*gross_desired[None,:]
    gap=np.maximum(0.0,required-scenario.stock_start[dest])
    return desired,current_f,step,gross_desired,gap


def inverse_depreciate_gap(gap:np.ndarray,data:ModelData,source:int,dest:int):
    # I_source enters at start source+1.  To arrive at dest-start, compensate for
    # depreciation in source+1 ... dest-1 using the corresponding annual D matrices.
    if dest<=source+1: return gap.copy()
    survival=np.ones_like(gap)
    for k in range(source+1,dest): survival*=1.0-data.dep_by_year[k]
    return np.divide(gap,survival,out=np.full_like(gap,np.inf),where=survival>1e-12)


def solve(data:ModelData,epsilon:float=DEFAULT_EPSILON,min_cv:float=DEFAULT_MIN_CV,maxiter:int=1500,gain_tol:float=1e-12)->SolveResult:
    T,N=data.goals.shape; inv=np.zeros((T,N,N),float)
    current=evaluate(data,inv); initial=current; transfers=[]; stop='maxiter'
    for it in range(1,maxiter+1):
        if current.cv_harmony<min_cv:
            return SolveResult(initial,current,transfers,'cv_threshold',it-1)
        dest=int(np.argmin(current.annual_harmony))
        if dest==0:
            return SolveResult(initial,current,transfers,'lowest_year_has_no_predecessor',it-1)
        desired,current_f,step,gross_desired,gap=capital_gap_for_harmony_step(data,current,dest,epsilon)
        if step<=gain_tol: return SolveResult(initial,current,transfers,'no_harmony_gap',it-1)
        if not np.isfinite(gap).all() or gap.sum()<=gain_tol:
            return SolveResult(initial,current,transfers,'no_capital_gap',it-1)
        best=None
        for src in range(dest):
            cand=inverse_depreciate_gap(gap,data,src,dest)
            if not np.isfinite(cand).all(): continue
            inv2=current.investments.copy(); inv2[src]+=cand
            v=evaluate(data,inv2)
            if np.min(v.feasible_ratio)<-1e-9: continue
            if np.min(v.net_social_output)<-1e-7: continue
            gain=v.mean_harmony-current.mean_harmony
            if gain>gain_tol and (best is None or gain>best[0]): best=(gain,src,cand,v)
        if best is None: return SolveResult(initial,current,transfers,'no_positive_transfer',it-1)
        gain,src,cand,new=best; bysrc=cand.sum(axis=1); bydest=cand.sum(axis=0)
        top_s=np.argsort(bysrc)[::-1][:5]; top_d=np.argsort(bydest)[::-1][:5]
        transfers.append({
            'iteration':it,'technology_mode':data.mode,'source_year':data.years[src],'destination_year':data.years[dest],
            'mean_harmony_before':current.mean_harmony,'mean_harmony_after':new.mean_harmony,'gain':gain,
            'cv_before':current.cv_harmony,'cv_after':new.cv_harmony,
            'destination_harmony_before':current.annual_harmony[dest],'destination_harmony_after':new.annual_harmony[dest],
            'current_worst_fulfillment':current_f,'desired_worst_fulfillment':desired,'step':step,
            'capital_at_destination_gap_real_musd':float(gap.sum()),'investment_at_source_real_musd':float(cand.sum()),
            'top_capital_sources':'; '.join(f'{data.sectors[i]}:{bysrc[i]:.3f}' for i in top_s if bysrc[i]>0),
            'top_capacity_destinations':'; '.join(f'{data.sectors[i]}:{bydest[i]:.3f}' for i in top_d if bydest[i]>0),
        })
        current=new
    return SolveResult(initial,current,transfers,stop,maxiter)


def sector_metrics(pred,obs):
    eps=1e-9; err=pred-obs
    wmape=float(np.sum(np.abs(err))/max(np.sum(np.abs(obs)),eps))
    corr=float(np.corrcoef(pred,obs)[0,1]) if np.std(pred)>0 and np.std(obs)>0 else float('nan')
    return {'wmape':wmape,'correlation':corr,'aggregate_ratio':float(pred.sum()/obs.sum()) if obs.sum()!=0 else float('nan')}


def export_result(data:ModelData,res:SolveResult,outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True)
    with open(outdir/'annual_path.csv','w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['year','initial_harmony','final_harmony','initial_feasible_ratio','final_feasible_ratio','initial_capital_constraint','final_capital_constraint','initial_labour_constraint','final_labour_constraint'])
        for t,y in enumerate(data.years):
            w.writerow([y,res.initial.annual_harmony[t],res.final.annual_harmony[t],res.initial.feasible_ratio[t],res.final.feasible_ratio[t],res.initial.capital_constraint[t],res.final.capital_constraint[t],res.initial.labour_constraint[t],res.final.labour_constraint[t]])
    with open(outdir/'investment_transfers.csv','w',newline='',encoding='utf-8') as f:
        if res.transfers:
            w=csv.DictWriter(f,fieldnames=list(res.transfers[0])); w.writeheader(); w.writerows(res.transfers)
        else: f.write('iteration,technology_mode,source_year,destination_year\n')
    summary=[]
    for t,y in enumerate(data.years):
        pg=res.final.gross_realized[t]; og=data.observed_gross[y]
        ps=res.final.stock_end[t].sum(axis=0); os=data.observed_stock[y]
        pi=res.final.investments[t].sum(axis=0); oi=data.observed_investment[y]
        mg=sector_metrics(pg,og); ms=sector_metrics(ps,os); mi=sector_metrics(pi,oi)
        summary.append({'year':y,'gross_wmape':mg['wmape'],'gross_corr':mg['correlation'],'gross_aggregate_ratio':mg['aggregate_ratio'],'stock_wmape':ms['wmape'],'stock_corr':ms['correlation'],'stock_aggregate_ratio':ms['aggregate_ratio'],'investment_wmape':mi['wmape'],'investment_corr':mi['correlation'],'investment_aggregate_ratio':mi['aggregate_ratio']})
        with open(outdir/f'sector_comparison_{y}.csv','w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(['bea_code','sector_name','gross_model_real','gross_observed_real','stock_model_end_real','stock_observed_end_real','investment_model_real','investment_observed_real'])
            for j,c in enumerate(data.sectors): w.writerow([c,data.names[c],pg[j],og[j],ps[j],os[j],pi[j],oi[j]])
    with open(outdir/'historical_comparison_summary.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    meta={'technology_mode':data.mode,'stop_reason':res.stop_reason,'iterations':res.iterations,'transfers':len(res.transfers),'initial_mean_harmony':res.initial.mean_harmony,'final_mean_harmony':res.final.mean_harmony,'initial_cv':res.initial.cv_harmony,'final_cv':res.final.cv_harmony,'epsilon':DEFAULT_EPSILON,'min_cv':DEFAULT_MIN_CV,'modifications':['M01 five-year objective horizon','M02 correct beginning/end-year stock timing','M03 marginal capacity-targeted accumulation','M04 71x71 capital composition preserved from Milestone B','M05 physical labour measured in BEA full-time equivalent employees','M06 2019-price volume quantities for output/capital/depreciation/investment','M07 annual A_t option with Frozen and Historical technology benchmarks']}
    (outdir/'RUN_METADATA.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')

if __name__=='__main__':
    here=Path(__file__).resolve().parents[1]; data_dir=here/'data'; results=here/'results'
    for mode in ('frozen','historical'):
        d=load_model_data(data_dir,mode); r=solve(d); export_result(d,r,results/mode)
        print(mode,json.dumps({'stop':r.stop_reason,'iterations':r.iterations,'transfers':len(r.transfers),'initial_mean_h':r.initial.mean_harmony,'final_mean_h':r.final.mean_harmony,'initial_cv':r.initial.cv_harmony,'final_cv':r.final.cv_harmony,'initial_h':r.initial.annual_harmony.tolist(),'final_h':r.final.annual_harmony.tolist()},indent=2))
