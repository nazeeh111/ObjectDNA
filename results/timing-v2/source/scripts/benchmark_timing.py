#!/usr/bin/env python3
"""Timing-only repeat of locked v2 modes, independent of quality-model selection.

Run after other owned rendering/test workloads have finished. This repeats the
same final-test scans only to measure runtime variability; models/settings are
fixed and no geometry or training decisions use these measurements.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[name]='1'
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
from threadpoolctl import threadpool_limits,threadpool_info
from objectdna.inference import reconstruct
from train import make_case

METHODS={'dense_geometric':dict(ranking='geometric',use_learned_proposal=False,candidate_mode='dense'),'compact_geometric':dict(ranking='geometric',use_learned_proposal=True,candidate_mode='learned_compact')}


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--repeats',type=int,default=3); parser.add_argument('--count',type=int,default=48); args=parser.parse_args()
    if not 3<=args.count<=48 or not 2<=args.repeats<=7: parser.error('Use 3–48 cases and 2–7 repeats.')
    test=ROOT/'results/compact-test-v2/summary.json'
    if not test.exists(): raise SystemExit('Complete the fixed v2 quality benchmark first.')
    quality=json.loads(test.read_text()); out=ROOT/'results/timing-v2'; out.mkdir(parents=True,exist_ok=True)
    versions={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('objectdna/geometry.py','objectdna/inference.py','objectdna/proposal.py','models/proposal.json','models/ranker.json','scripts/benchmark_timing.py')}
    for name,sha in versions.items():
        if name in quality['source_versions'] and quality['source_versions'][name]!=sha: raise SystemExit(f'Locked v2 source/model changed: {name}. Inspect before timing.')
    started=time.perf_counter(); rows=[]
    with threadpool_limits(limits=1):
        warm_scan=make_case(2000)[1]
        for method,settings in METHODS.items(): reconstruct(warm_scan,units='mm',refine=True,**settings)
        pools=[{k:v for k,v in item.items() if k!='filepath'} for item in threadpool_info()]
        scans={seed:make_case(seed)[1] for seed in quality['seeds'][:args.count]}
        for repeat in range(args.repeats):
            order=list(scans); np.random.default_rng(271+repeat).shuffle(order)
            for seed in order:
                methods=list(METHODS); np.random.default_rng(seed+991*repeat).shuffle(methods)
                for method in methods:
                    result=reconstruct(scans[seed],units='mm',refine=True,**METHODS[method])
                    rows.append({'seed':seed,'repeat':repeat,'method':method,'seconds':result['runtime_seconds'],'candidate_count':result['provenance']['candidate_count']})
            (out/'cases.json').write_text(json.dumps(rows,indent=2)+'\n'); print(f'timing repeat{repeat+1}/{args.repeats} complete',flush=True)
    by_case=[]
    for seed in scans:
        row={'seed':seed}
        for method in METHODS: row[method]=float(np.median([r['seconds'] for r in rows if r['seed']==seed and r['method']==method]))
        row['speedup']=row['dense_geometric']/row['compact_geometric']; row['difference_seconds']=row['compact_geometric']-row['dense_geometric']; by_case.append(row)
    dense=np.array([r['dense_geometric'] for r in by_case]); compact=np.array([r['compact_geometric'] for r in by_case]); rng=np.random.default_rng(281); boot=rng.integers(0,len(dense),(5000,len(dense)))
    ratio=dense[boot].mean(1)/compact[boot].mean(1); difference=(compact[boot]-dense[boot]).mean(1)
    unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in versions.items())
    summary={'schema_version':1,'cases':len(scans),'repeats':args.repeats,'warmup':'Both modes once on training seed 2000, excluded','statistic':'Median of repeat times per object per method; then aggregate across paired objects','dense_mean_of_case_medians_seconds':float(dense.mean()),'compact_mean_of_case_medians_seconds':float(compact.mean()),'dense_median_of_case_medians_seconds':float(np.median(dense)),'compact_median_of_case_medians_seconds':float(np.median(compact)),'ratio_of_mean_case_medians':float(dense.mean()/compact.mean()),'median_per_case_speedup':float(np.median(dense/compact)),'speedup_bootstrap_95_percentile_ci':np.quantile(ratio,[.025,.975]).tolist(),'paired_mean_difference_seconds':float((compact-dense).mean()),'difference_bootstrap_95_percentile_ci':np.quantile(difference,[.025,.975]).tolist(),'source_unchanged_during_run':unchanged,'source_versions':versions,'quality_report_sha256':hashlib.sha256(test.read_bytes()).hexdigest(),'threadpools':pools,'environment':{'python':platform.python_version(),'platform':platform.platform(),'numpy':np.__version__},'total_seconds':time.perf_counter()-started,'limits':['Timing-only repeat of fixed modes on already evaluated scans; no tuning, retraining or quality selection.','Observed runtime is production reconstruction wall time, excluding cold imports, CAD validation/export and benchmark-only ground-truth metrics.','One BLAS/OpenMP thread requested; method order and object order randomized on every repeat.','Run after heavyweight owned test/render tasks finished; unrelated system load remains uncontrolled.','Exploratory paired bootstrap over 48 synthetic objects is not a universal speed guarantee.']}
    (out/'case_medians.json').write_text(json.dumps(by_case,indent=2)+'\n'); (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lo,hi=summary['speedup_bootstrap_95_percentile_ci']; dlo,dhi=summary['difference_bootstrap_95_percentile_ci']
    (out/'REPORT.md').write_text(f'''# Locked v2 timing repeat

{len(scans)} paired synthetic scans × {args.repeats} repeats, balanced randomized method/object order, warmup excluded. One BLAS/OpenMP thread requested. Source unchanged during run: {unchanged}.

| Mode | Mean of per-case medians (s) | Median of per-case medians (s) |
|---|---:|---:|
| Dense geometric | {dense.mean():.4f} | {np.median(dense):.4f} |
| Learned compact + geometry | {compact.mean():.4f} | {np.median(compact):.4f} |

Ratio of mean case medians: **{summary['ratio_of_mean_case_medians']:.2f}×**, exploratory paired bootstrap 95% interval [{lo:.2f}, {hi:.2f}]. Median per-case speedup: {summary['median_per_case_speedup']:.2f}×. Compact-minus-dense mean paired difference: {summary['paired_mean_difference_seconds']:+.4f}s, interval [{dlo:+.4f}, {dhi:+.4f}].

'''+ '\n'.join('- '+s for s in summary['limits'])+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
