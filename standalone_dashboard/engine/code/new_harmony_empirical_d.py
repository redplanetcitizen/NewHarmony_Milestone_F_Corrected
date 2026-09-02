from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import csv, json
import numpy as np

import new_harmony_empirical_c as c

DEFAULT_EPSILON = c.DEFAULT_EPSILON
DEFAULT_MIN_CV = c.DEFAULT_MIN_CV
GAIN_TOL = 1e-12


def _read_matrix(path: Path, sectors: list[str]) -> np.ndarray:
    rows = list(csv.reader(open(path, encoding='utf-8-sig', newline='')))
    hdr = [x.strip() for x in rows[0][1:]]
    rowcodes = [r[0].strip() for r in rows[1:]]
    raw = np.array([[float(x) for x in r[1:]] for r in rows[1:]], float)
    rid = {v:i for i,v in enumerate(rowcodes)}
    cid = {v:i for i,v in enumerate(hdr)}
    return raw[np.ix_([rid[s] for s in sectors],[cid[s] for s in sectors])]


def _read_vector(path: Path, sectors: list[str]) -> np.ndarray:
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    val = [k for k in rows[0] if k not in ('bea_code','sector_name')][0]
    by = {r['bea_code']:float(r[val]) for r in rows}
    return np.array([by[s] for s in sectors], float)


@dataclass
class TradeInventoryData:
    import_A_by_year: np.ndarray
    import_cap_by_year: np.ndarray
    inventory_change_real: np.ndarray
    inventory_flow_envelope: np.ndarray


@dataclass
class DScenario:
    investments: np.ndarray
    inventory_transfers: np.ndarray
    stock_start: np.ndarray
    stock_end: np.ndarray
    gross_required: np.ndarray
    gross_realized: np.ndarray
    total_final_required: np.ndarray
    net_social_output: np.ndarray
    fulfillment: np.ndarray
    annual_harmony: np.ndarray
    mean_harmony: float
    std_harmony: float
    cv_harmony: float
    capital_constraint: np.ndarray
    labour_constraint: np.ndarray
    import_constraint: np.ndarray
    production_scale: np.ndarray
    feasible_ratio: np.ndarray
    imported_intermediate_required: np.ndarray
    imported_intermediate_cap: np.ndarray
    inventory_accumulation: np.ndarray
    inventory_release: np.ndarray
    inventory_start: np.ndarray
    inventory_end: np.ndarray


@dataclass
class DSolveResult:
    initial: DScenario
    final: DScenario
    capital_transfers: list[dict]
    inventory_transfers_log: list[dict]
    stop_reason_capital: str
    stop_reason_inventory: str
    capital_iterations: int
    inventory_iterations: int


def load_trade_inventory(data: c.ModelData, data_dir: Path) -> TradeInventoryData:
    T, N = data.goals.shape
    import_A = np.zeros((T,N,N), float)
    import_cap = np.zeros((T,N), float)
    for t,y in enumerate(data.years):
        ratio_year = 2019 if data.mode == 'frozen' else y
        R = _read_matrix(data_dir/f'intermediate_import_to_domestic_ratio_{ratio_year}.csv', data.sectors)
        import_A[t] = np.maximum(data.A_by_year[t],0.0) * np.maximum(R,0.0)
        # Model-consistent real import envelope.  At observed domestic gross output,
        # the published import-share overlay exactly defines the cap in the same
        # 2019-price coefficient space used by Milestone C.
        import_cap[t] = import_A[t] @ data.observed_gross[y]

    inv_rows = list(csv.DictReader(open(data_dir/'inventory_change_F030_nominal.csv', encoding='utf-8-sig')))
    inv_real = np.zeros((T,N), float)
    for t,y in enumerate(data.years):
        nom = {r['bea_code']:float(r['inventory_change_domestic_musd']) for r in inv_rows if int(r['year'])==y}
        p = _read_vector(data_dir/f'gross_output_price_relative_{y}.csv', data.sectors)
        inv_real[t] = np.array([nom[s] for s in data.sectors],float) / p
    return TradeInventoryData(import_A, import_cap, inv_real, np.abs(inv_real))


def _validate_inventory_tensor(transfers: np.ndarray, T: int, N: int) -> None:
    if transfers.shape != (T,T,N) or not np.isfinite(transfers).all() or np.any(transfers < -1e-12):
        raise ValueError('inventory transfer tensor must be finite, nonnegative, T x T x N')
    for src in range(T):
        if np.any(transfers[src,:src+1] > 1e-12):
            raise ValueError('inventory transfers must be strictly forward in time')


def evaluate_d(data: c.ModelData, trade: TradeInventoryData, investments: np.ndarray,
               inventory_transfers: np.ndarray | None = None, *, imports_enabled: bool = True,
               inventories_enabled: bool = True) -> DScenario:
    T,N = data.goals.shape
    if inventory_transfers is None:
        inventory_transfers = np.zeros((T,T,N), float)
    inventory_transfers = np.asarray(inventory_transfers,float)
    if not inventories_enabled:
        inventory_transfers = np.zeros((T,T,N),float)
    _validate_inventory_tensor(inventory_transfers,T,N)

    accum = inventory_transfers.sum(axis=1)
    release = inventory_transfers.sum(axis=0)
    if np.any(release - data.goals > 1e-8):
        raise ValueError('inventory release cannot exceed the social target component')

    stock_start=np.zeros((T,N,N)); stock_end=np.zeros_like(stock_start)
    gross_req=np.zeros((T,N)); gross_real=np.zeros_like(gross_req)
    total_final=np.zeros_like(gross_req); net_social=np.zeros_like(gross_req)
    fulfill=np.full_like(gross_req,np.nan)
    hc=np.zeros(T); lc=np.zeros(T); mc=np.full(T,np.inf)
    prod_scale=np.zeros(T); fr=np.zeros(T); ah=np.zeros(T)
    im_req=np.zeros((T,N)); im_cap=np.zeros((T,N))
    qstart=np.zeros((T,N)); qend=np.zeros((T,N))
    stock_start[0]=data.initial_stock

    for t in range(T):
        if t>0:
            stock_start[t]=stock_end[t-1]
            qstart[t]=qend[t-1]

        residual_goal=np.maximum(data.goals[t]-release[t],0.0)
        inv_by_source=investments[t].sum(axis=1)
        fixed_final=inv_by_source+accum[t]
        total_final[t]=residual_goal+fixed_final
        L=data.L_by_year[t]
        gross_social=L@residual_goal
        gross_fixed=L@fixed_final
        gross_req[t]=gross_social+gross_fixed

        cap_limit=np.full(N,np.inf)
        for j in range(N):
            mask=data.C[:,j]>1e-12
            if np.any(mask):
                cap_limit[j]=float(np.min(stock_start[t,mask,j]/data.C[mask,j]))
        cap_bounds=[]; fixed_feasible=True
        for j in range(N):
            if gross_fixed[j]>cap_limit[j]+1e-8:
                fixed_feasible=False
            if gross_social[j]>1e-12:
                cap_bounds.append((cap_limit[j]-gross_fixed[j])/gross_social[j])
        hc[t]=float(min(cap_bounds)) if cap_bounds else np.inf

        lcoef=data.labour_coeff_by_year[t]
        lab_social=float(lcoef@gross_social); lab_fixed=float(lcoef@gross_fixed)
        lc[t]=float((data.labour_available[t]-lab_fixed)/lab_social) if lab_social>1e-12 else np.inf

        if imports_enabled:
            A_m=trade.import_A_by_year[t]; cap=trade.import_cap_by_year[t]
            imp_fixed=A_m@gross_fixed; imp_social=A_m@gross_social
            if np.any(imp_fixed>cap+1e-8):
                fixed_feasible=False
            bounds=np.divide(cap-imp_fixed,imp_social,out=np.full(N,np.inf),where=imp_social>1e-12)
            mc[t]=float(np.min(bounds))
            im_cap[t]=cap
        else:
            A_m=np.zeros((N,N)); mc[t]=np.inf; im_cap[t]=np.full(N,np.inf)

        raw_f=min(hc[t],lc[t],mc[t])
        if not fixed_feasible:
            raw_f=min(raw_f,-1.0)
        f=max(0.0,raw_f)
        prod_scale[t]=f
        gross_real[t]=gross_fixed+f*gross_social
        if imports_enabled:
            im_req[t]=trade.import_A_by_year[t]@gross_real[t]

        delivered=release[t]+f*residual_goal
        net_social[t]=delivered
        mask=data.goals[t]>1e-12
        if np.any(mask):
            fulfill[t,mask]=delivered[mask]/data.goals[t,mask]
            fr[t]=float(np.min(fulfill[t,mask]))
        else:
            fr[t]=1.0
        ah[t]=float(c.harmony(fr[t]))

        stock_end[t]=stock_start[t]*(1.0-data.dep_by_year[t])+investments[t]
        qend[t]=qstart[t]+accum[t]-release[t]
        if np.any(qend[t] < -1e-7):
            raise ValueError('planner inventory cannot become negative')
        qend[t]=np.maximum(qend[t],0.0)

    mean=float(np.mean(ah)); std=float(np.std(ah,ddof=1)); cv=std/abs(mean) if mean!=0 else np.inf
    return DScenario(investments.copy(),inventory_transfers.copy(),stock_start,stock_end,gross_req,gross_real,total_final,
                     net_social,fulfill,ah,mean,std,cv,hc,lc,mc,prod_scale,fr,im_req,im_cap,accum,release,qstart,qend)


def capital_gap_for_harmony_step(data: c.ModelData, scenario: DScenario, dest: int, epsilon: float):
    target_f=float(c.harmony_inverse(scenario.mean_harmony))
    current_f=float(c.harmony_inverse(scenario.annual_harmony[dest]))
    diff=max(0.0,target_f-current_f); step=diff*epsilon; desired=current_f+step
    inv_by_source=scenario.investments[dest].sum(axis=1)
    desired_final=data.goals[dest]*desired+inv_by_source
    gross_desired=data.L_by_year[dest]@desired_final
    required=data.C*gross_desired[None,:]
    gap=np.maximum(0.0,required-scenario.stock_start[dest])
    return desired,current_f,step,gross_desired,gap


def inverse_depreciate_gap(gap: np.ndarray, data: c.ModelData, source: int, dest: int):
    if dest<=source+1:
        return gap.copy()
    survival=np.ones_like(gap)
    for k in range(source+1,dest):
        survival*=1.0-data.dep_by_year[k]
    return np.divide(gap,survival,out=np.full_like(gap,np.inf),where=survival>1e-12)


def solve_capital_d(data: c.ModelData, trade: TradeInventoryData, *, imports_enabled: bool,
                    epsilon: float=DEFAULT_EPSILON, min_cv: float=DEFAULT_MIN_CV,
                    maxiter: int=1500, gain_tol: float=GAIN_TOL):
    T,N=data.goals.shape
    inv=np.zeros((T,N,N),float); q=np.zeros((T,T,N),float)
    current=evaluate_d(data,trade,inv,q,imports_enabled=imports_enabled,inventories_enabled=False)
    initial=current; transfers=[]; stop='maxiter'
    for it in range(1,maxiter+1):
        if current.cv_harmony<min_cv:
            return initial,current,transfers,'cv_threshold',it-1
        dest=int(np.argmin(current.annual_harmony))
        if dest==0:
            return initial,current,transfers,'lowest_year_has_no_predecessor',it-1
        desired,current_f,step,gross_desired,gap=capital_gap_for_harmony_step(data,current,dest,epsilon)
        if step<=gain_tol:
            return initial,current,transfers,'no_harmony_gap',it-1
        if not np.isfinite(gap).all() or gap.sum()<=gain_tol:
            return initial,current,transfers,'no_capital_gap',it-1
        best=None
        for src in range(dest):
            cand=inverse_depreciate_gap(gap,data,src,dest)
            if not np.isfinite(cand).all():
                continue
            inv2=current.investments.copy(); inv2[src]+=cand
            v=evaluate_d(data,trade,inv2,q,imports_enabled=imports_enabled,inventories_enabled=False)
            if np.min(v.production_scale)<-1e-9 or np.min(v.net_social_output)<-1e-7:
                continue
            if imports_enabled and np.any(v.imported_intermediate_required-v.imported_intermediate_cap>1e-7):
                continue
            gain=v.mean_harmony-current.mean_harmony
            if gain>gain_tol and (best is None or gain>best[0]):
                best=(gain,src,cand,v)
        if best is None:
            return initial,current,transfers,'no_positive_transfer',it-1
        gain,src,cand,new=best
        bysrc=cand.sum(axis=1); bydest=cand.sum(axis=0)
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
    return initial,current,transfers,stop,maxiter


def balance_inventories(data: c.ModelData, trade: TradeInventoryData, capital_scenario: DScenario,
                        *, imports_enabled: bool=True, epsilon: float=DEFAULT_EPSILON,
                        min_cv: float=DEFAULT_MIN_CV, maxiter: int=3000, gain_tol: float=GAIN_TOL):
    """Search conservative, empirical-envelope inventory transfers.

    The accepted backtest does not assume an unobserved 2018 absolute inventory stock.
    A planner transfer must be produced in an earlier modeled year and released later.
    Its positive/negative annual flow by sector is capped by the absolute real F030
    movement observed for that year and sector.  This is a conservative throughput
    envelope, not an estimate of warehouse stock capacity.
    """
    T,N=data.goals.shape
    tensor=np.zeros((T,T,N),float)
    current=evaluate_d(data,trade,capital_scenario.investments,tensor,imports_enabled=imports_enabled,inventories_enabled=True)
    initial=current; logs=[]; stop='maxiter'
    env=trade.inventory_flow_envelope
    for it in range(1,maxiter+1):
        if current.cv_harmony<min_cv:
            return initial,current,tensor,logs,'cv_threshold',it-1
        dest=int(np.argmin(current.annual_harmony))
        if dest==0:
            return initial,current,tensor,logs,'lowest_year_has_no_predecessor',it-1
        target_f=float(c.harmony_inverse(current.mean_harmony))
        current_f=float(current.feasible_ratio[dest])
        diff=max(0.0,target_f-current_f)
        if diff<=gain_tol:
            return initial,current,tensor,logs,'no_harmony_gap',it-1
        net=current.inventory_accumulation-current.inventory_release
        best=None
        for src in range(dest):
            src_used=np.maximum(net[src],0.0)
            dest_used=np.maximum(-net[dest],0.0)
            for i in range(N):
                if data.goals[dest,i]<=1e-12:
                    continue
                src_room=max(0.0,env[src,i]-src_used[i])
                dest_room=max(0.0,env[dest,i]-dest_used[i])
                target_room=max(0.0,data.goals[dest,i]-current.inventory_release[dest,i])
                amount=min(diff*epsilon*data.goals[dest,i],src_room,dest_room,target_room)
                if amount<=gain_tol:
                    continue
                t2=tensor.copy(); t2[src,dest,i]+=amount
                try:
                    v=evaluate_d(data,trade,capital_scenario.investments,t2,imports_enabled=imports_enabled,inventories_enabled=True)
                except ValueError:
                    continue
                if imports_enabled and np.any(v.imported_intermediate_required-v.imported_intermediate_cap>1e-7):
                    continue
                gain=v.mean_harmony-current.mean_harmony
                if gain>gain_tol and (best is None or gain>best[0]):
                    best=(gain,src,i,amount,v,t2)
        if best is None:
            return initial,current,tensor,logs,'no_positive_inventory_transfer',it-1
        gain,src,i,amount,new,tensor=best
        logs.append({
            'iteration':it,'technology_mode':data.mode,'source_year':data.years[src],
            'destination_year':data.years[dest],'bea_code':data.sectors[i],'sector_name':data.names[data.sectors[i]],
            'amount_real_2019price_musd':float(amount),'mean_harmony_before':current.mean_harmony,
            'mean_harmony_after':new.mean_harmony,'gain':gain,'cv_before':current.cv_harmony,'cv_after':new.cv_harmony,
        })
        current=new
    return initial,current,tensor,logs,stop,maxiter


def solve_configuration(data: c.ModelData, trade: TradeInventoryData, *, imports_enabled: bool, inventories_enabled: bool) -> DSolveResult:
    if not imports_enabled and not inventories_enabled:
        # Strict predecessor replay branch.  No arithmetic is inserted ahead of C.
        rc=c.solve(data)
        base=evaluate_d(data,trade,rc.initial.investments,imports_enabled=False,inventories_enabled=False)
        fin=evaluate_d(data,trade,rc.final.investments,imports_enabled=False,inventories_enabled=False)
        return DSolveResult(base,fin,rc.transfers,[],rc.stop_reason,'disabled',rc.iterations,0)

    ci,cf,clog,cstop,citers=solve_capital_d(data,trade,imports_enabled=imports_enabled)
    if inventories_enabled:
        ii,final,tensor,ilog,istop,iiters=balance_inventories(data,trade,cf,imports_enabled=imports_enabled)
        # `initial` means beginning of the full D configuration (before capital changes).
        return DSolveResult(ci,final,clog,ilog,cstop,istop,citers,iiters)
    return DSolveResult(ci,cf,clog,[],cstop,'disabled',citers,0)


def sector_metrics(pred,obs):
    return c.sector_metrics(pred,obs)


def export_result(data: c.ModelData, trade: TradeInventoryData, res: DSolveResult, outdir: Path,
                  *, imports_enabled: bool, inventories_enabled: bool):
    outdir.mkdir(parents=True,exist_ok=True)
    f=res.final
    with open(outdir/'annual_path.csv','w',newline='',encoding='utf-8') as stream:
        w=csv.writer(stream)
        w.writerow(['year','initial_harmony','final_harmony','initial_fulfillment','final_fulfillment','final_production_scale','capital_constraint','labour_constraint','import_constraint'])
        for t,y in enumerate(data.years):
            w.writerow([y,res.initial.annual_harmony[t],f.annual_harmony[t],res.initial.feasible_ratio[t],f.feasible_ratio[t],f.production_scale[t],f.capital_constraint[t],f.labour_constraint[t],f.import_constraint[t]])
    with open(outdir/'investment_transfers.csv','w',newline='',encoding='utf-8') as stream:
        if res.capital_transfers:
            w=csv.DictWriter(stream,fieldnames=list(res.capital_transfers[0])); w.writeheader(); w.writerows(res.capital_transfers)
        else:
            stream.write('iteration,technology_mode,source_year,destination_year\n')
    with open(outdir/'inventory_transfers.csv','w',newline='',encoding='utf-8') as stream:
        if res.inventory_transfers_log:
            w=csv.DictWriter(stream,fieldnames=list(res.inventory_transfers_log[0])); w.writeheader(); w.writerows(res.inventory_transfers_log)
        else:
            stream.write('iteration,technology_mode,source_year,destination_year,bea_code,sector_name,amount_real_2019price_musd,mean_harmony_before,mean_harmony_after,gain,cv_before,cv_after\n')
    with open(outdir/'import_balance.csv','w',newline='',encoding='utf-8') as stream:
        w=csv.writer(stream); w.writerow(['year','bea_code','sector_name','required_imported_intermediate_real','import_cap_real','slack_real','required_over_cap'])
        for t,y in enumerate(data.years):
            for i,code in enumerate(data.sectors):
                req=f.imported_intermediate_required[t,i]
                cap=f.imported_intermediate_cap[t,i]
                ratio=req/cap if np.isfinite(cap) and cap>1e-12 else 0.0
                w.writerow([y,code,data.names[code],req,cap,cap-req if np.isfinite(cap) else np.inf,ratio])
    with open(outdir/'inventory_state.csv','w',newline='',encoding='utf-8') as stream:
        w=csv.writer(stream); w.writerow(['year','bea_code','sector_name','modeled_start_inventory','modeled_accumulation','modeled_release','modeled_end_inventory','observed_F030_real_change','empirical_abs_flow_envelope'])
        for t,y in enumerate(data.years):
            for i,code in enumerate(data.sectors):
                w.writerow([y,code,data.names[code],f.inventory_start[t,i],f.inventory_accumulation[t,i],f.inventory_release[t,i],f.inventory_end[t,i],trade.inventory_change_real[t,i],trade.inventory_flow_envelope[t,i]])
    summary=[]
    for t,y in enumerate(data.years):
        pg=f.gross_realized[t]; og=data.observed_gross[y]
        ps=f.stock_end[t].sum(axis=0); os=data.observed_stock[y]
        pi=f.investments[t].sum(axis=0); oi=data.observed_investment[y]
        mg=sector_metrics(pg,og); ms=sector_metrics(ps,os); mi=sector_metrics(pi,oi)
        summary.append({'year':y,'gross_wmape':mg['wmape'],'gross_corr':mg['correlation'],'gross_aggregate_ratio':mg['aggregate_ratio'],'stock_wmape':ms['wmape'],'stock_corr':ms['correlation'],'stock_aggregate_ratio':ms['aggregate_ratio'],'investment_wmape':mi['wmape'],'investment_corr':mi['correlation'],'investment_aggregate_ratio':mi['aggregate_ratio'],'import_required_sum':float(f.imported_intermediate_required[t].sum()),'import_cap_sum':float(f.imported_intermediate_cap[t].sum()) if imports_enabled else 0.0,'inventory_net_change_sum':float((f.inventory_accumulation[t]-f.inventory_release[t]).sum())})
    with open(outdir/'historical_comparison_summary.csv','w',newline='',encoding='utf-8') as stream:
        w=csv.DictWriter(stream,fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    meta={'technology_mode':data.mode,'imports_enabled':imports_enabled,'inventories_enabled':inventories_enabled,
          'stop_reason_capital':res.stop_reason_capital,'stop_reason_inventory':res.stop_reason_inventory,
          'capital_transfers':len(res.capital_transfers),'inventory_transfers':len(res.inventory_transfers_log),
          'initial_mean_harmony':res.initial.mean_harmony,'final_mean_harmony':f.mean_harmony,
          'initial_cv':res.initial.cv_harmony,'final_cv':f.cv_harmony,
          'M08_import_cap':'componentwise model-consistent real envelope: A_import[t] @ observed domestic gross output[t]',
          'M09_inventory_envelope':'absolute real domestic F030 movement by sector/year; conservative flow-throughput proxy, not stock capacity'}
    (outdir/'RUN_METADATA.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')


def write_real_inventory_file(data: c.ModelData, trade: TradeInventoryData, out: Path):
    with open(out,'w',newline='',encoding='utf-8') as stream:
        w=csv.writer(stream); w.writerow(['year','bea_code','sector_name','inventory_change_domestic_real_2019price_musd','abs_flow_envelope_real_2019price_musd'])
        for t,y in enumerate(data.years):
            for i,code in enumerate(data.sectors):
                w.writerow([y,code,data.names[code],trade.inventory_change_real[t,i],trade.inventory_flow_envelope[t,i]])


def run_all(root: Path):
    data_dir=root/'data'; results=root/'results'
    configs=[('c_replay',False,False),('m08_only',True,False),('m08_m09',True,True)]
    headline=[]; annual=[]
    for mode in ('frozen','historical'):
        data=c.load_model_data(data_dir,mode); trade=load_trade_inventory(data,data_dir)
        if mode=='frozen':
            write_real_inventory_file(data,trade,data_dir/'inventory_change_F030_real_2019price.csv')
        for label,imp,inv in configs:
            res=solve_configuration(data,trade,imports_enabled=imp,inventories_enabled=inv)
            out=results/label/mode; export_result(data,trade,res,out,imports_enabled=imp,inventories_enabled=inv)
            rows=list(csv.DictReader(open(out/'historical_comparison_summary.csv',encoding='utf-8')))
            gross_ratio=sum(res.final.gross_realized[t].sum() for t in range(5))/sum(data.observed_gross[y].sum() for y in data.years)
            inv_ratio=sum(res.final.investments[t].sum() for t in range(5))/sum(data.observed_investment[y].sum() for y in data.years)
            stock_ratio=res.final.stock_end[-1].sum()/data.observed_stock[2023].sum()
            headline.append({'configuration':label,'technology_mode':mode,'capital_stop':res.stop_reason_capital,'inventory_stop':res.stop_reason_inventory,'capital_transfers':len(res.capital_transfers),'inventory_transfers':len(res.inventory_transfers_log),'initial_mean_harmony':res.initial.mean_harmony,'final_mean_harmony':res.final.mean_harmony,'initial_cv':res.initial.cv_harmony,'final_cv':res.final.cv_harmony,'five_year_gross_aggregate_ratio':gross_ratio,'stock_2023_aggregate_ratio':stock_ratio,'five_year_investment_aggregate_ratio':inv_ratio,'five_year_import_required_real':float(res.final.imported_intermediate_required.sum()),'five_year_import_cap_real':float(res.final.imported_intermediate_cap[np.isfinite(res.final.imported_intermediate_cap)].sum()) if imp else 0.0,'modeled_inventory_abs_net_flow_real':float(np.abs(res.final.inventory_accumulation-res.final.inventory_release).sum())})
            for t,y in enumerate(data.years):
                annual.append({'configuration':label,'technology_mode':mode,'year':y,'harmony':res.final.annual_harmony[t],'fulfillment':res.final.feasible_ratio[t],'production_scale':res.final.production_scale[t],'import_required':float(res.final.imported_intermediate_required[t].sum()),'import_cap':float(res.final.imported_intermediate_cap[t].sum()) if imp else 0.0,'inventory_net_change':float((res.final.inventory_accumulation[t]-res.final.inventory_release[t]).sum())})
    with open(results/'comparison'/'BENCHMARK_HEADLINE.csv','w',newline='',encoding='utf-8') as stream:
        w=csv.DictWriter(stream,fieldnames=list(headline[0])); w.writeheader(); w.writerows(headline)
    with open(results/'comparison'/'BENCHMARK_ANNUAL.csv','w',newline='',encoding='utf-8') as stream:
        w=csv.DictWriter(stream,fieldnames=list(annual[0])); w.writeheader(); w.writerows(annual)
    return headline


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    rows=run_all(root)
    print(json.dumps(rows,indent=2))
