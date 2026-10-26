#!/usr/bin/env python3
"""Run fixed, disjoint held-out synthetic evaluation and save every measurement."""
from __future__ import annotations
import argparse
import copy
import csv
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ.setdefault(name,'1')
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
from scipy.spatial import cKDTree
from objectdna.geometry import sample_surface, occupancy, chamfer
from objectdna.inference import reconstruct, load_ranker
from objectdna.cad import shape_stats, validate_spec
from train import make_case, canonical_hash, TEST_SEEDS


def measure(spec,truth,translation,seed):
    a=sample_surface(truth,7000,seed+50000)
    b=sample_surface(spec,7000,seed+50001)+translation
    # Independent random samples give a nonzero nearest-neighbor sampling floor.
    floor=chamfer(a,sample_surface(truth,7000,seed+50002))
    low=np.minimum(0,translation)
    high=np.maximum([truth['parameters'][k] for k in ('width','depth','height')],np.array([spec['parameters'][k] for k in ('width','depth','height')])+translation)
    points=np.random.default_rng(seed+50003).uniform(low,high,(50000,3))
    x=occupancy(points,truth); y=occupancy(points-translation,spec)
    iou=float((x&y).sum()/max((x|y).sum(),1))
    dimensions={k:abs(spec['parameters'][k]-truth['parameters'][k]) for k in ('width','depth','height')}
    matched=spec['family']==truth['family']
    thickness=abs(spec['parameters']['thickness']-truth['parameters']['thickness']) if matched and truth['family']!='block' else None
    t0=time.perf_counter(); stats=shape_stats(spec)
    edited=copy.deepcopy(spec); edited['parameters']['width']*=1.1
    edit_stats=shape_stats(edited)
    edit_ok=bool(edit_stats['valid'] and edit_stats['solid_count']==1 and abs(edit_stats['bounds_mm']['size'][0]-edited['parameters']['width'])<1e-5)
    return {'chamfer_mm':chamfer(a,b),'sampling_floor_mm':floor,'volumetric_iou':iou,'external_dim_mae_mm':float(np.mean(list(dimensions.values()))),'external_dimension_errors_mm':dimensions,'thickness_error_mm':thickness,'family_correct':matched,'hole_count_correct':len(spec.get('holes',[]))==len(truth.get('holes',[])) if matched and truth['family']=='block' else None,'cad_valid':bool(stats['valid'] and stats['solid_count']==1),'editable':edit_ok,'validation_seconds':time.perf_counter()-t0,'volume_mm3':stats['volume_mm3']}


def aggregate(rows):
    good=[r for r in rows if r.get('error') is None]
    result={'cases':len(rows),'completed':len(good),'failures':len(rows)-len(good)}
    for field in ('chamfer_mm','sampling_floor_mm','volumetric_iou','external_dim_mae_mm','thickness_error_mm','runtime_seconds','validation_seconds'):
        values=[r[field] for r in good if r.get(field) is not None]
        result[field+'_mean']=float(np.mean(values)) if values else None
        result[field+'_median']=float(np.median(values)) if values else None
    for field in ('family_correct','cad_valid','editable','hole_count_correct'):
        values=[r[field] for r in good if r.get(field) is not None]
        result[field+'_rate']=float(np.mean(values)) if values else None
        result[field+'_denominator']=len(values)
    return result


def paired_interval(rows,method_a,method_b,metric):
    # Return B minus A; negative is a distance improvement, positive an IoU improvement.
    a={r['seed']:r for r in rows if r['method']==method_a and r.get('error') is None}
    b={r['seed']:r for r in rows if r['method']==method_b and r.get('error') is None}
    ids=sorted(a.keys()&b.keys()); values=np.array([b[i][metric]-a[i][metric] for i in ids])
    rng=np.random.default_rng(173); boot=np.mean(values[rng.integers(0,len(values),(5000,len(values)))],axis=1)
    return {'comparison':f'{method_b} minus {method_a}','metric':metric,'paired_cases':len(ids),'mean':float(values.mean()),'bootstrap_95_percentile_ci':np.quantile(boot,[.025,.975]).tolist(),'interpretation':'Exploratory paired interval over synthetic cases; not a claim about unseen real objects.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--count',type=int,default=48); parser.add_argument('--out',type=Path,default=ROOT/'results/synthetic-v1'); args=parser.parse_args()
    if not 3<=args.count<=48: parser.error('--count must be 3–48.')
    model=load_ranker()
    if model is None: raise SystemExit('Train first: python scripts/train.py')
    manifest=json.loads((ROOT/'models/training_manifest.json').read_text())
    if canonical_hash(manifest)!=model['training_manifest_sha256']: raise SystemExit('Model/manifest hash mismatch; regenerate training.')
    methods=('bbox','geometric_refined','learned_no_proposal','learned_unrefined','learned_refined'); rows=[]; cases=[]
    start=time.perf_counter()
    for n,seed in enumerate(list(TEST_SEEDS)[:args.count]):
        truth,scan,cloud,dims,pose,record=make_case(seed); cases.append(record)
        for method in methods:
            row={'seed':seed,'method':method,'truth_family':truth['family'],'partial':record['partial'],'noise_fraction_diagonal':record['noise_fraction_diagonal']}
            try:
                t0=time.perf_counter()
                if method=='bbox':
                    spec={'family':'block','parameters':dict(zip(('width','depth','height'),map(float,dims))), 'holes':[]}; spec['parameters']['thickness']=float(min(dims)*.1)
                    runtime=time.perf_counter()-t0; translation=np.array(pose['translation'])
                else:
                    result=reconstruct(scan,units='mm',ranking='geometric' if method=='geometric_refined' else 'learned',refine=method!='learned_unrefined',use_learned_proposal=method not in ('geometric_refined','learned_no_proposal'))
                    spec=result['spec']; runtime=result['runtime_seconds']; translation=np.asarray(result['provenance']['transform']['translation'])
                    row.update(accepted=result['metrics']['accepted'],observed_support=result['metrics']['observed_support'],surface_coverage=result['metrics']['surface_coverage'])
                row.update(spec=spec,predicted_family=spec['family'],runtime_seconds=runtime,**measure(spec,truth,translation,seed))
            except Exception as exc:
                row['error']=f'{type(exc).__name__}: {exc}'
            rows.append(row)
        print(f'held-out {n+1}/{args.count}: truth={truth["family"]} '+', '.join(f'{r["method"]}={r.get("volumetric_iou",r.get("error"))}' for r in rows[-len(methods):]),flush=True)
        args.out.mkdir(parents=True,exist_ok=True); (args.out/'cases.json').write_text(json.dumps(rows,indent=2)+'\n')
    aggregates={method:aggregate([r for r in rows if r['method']==method]) for method in methods}
    comparisons=[paired_interval(rows,'geometric_refined','learned_refined',metric) for metric in ('chamfer_mm','volumetric_iou')]+[paired_interval(rows,'learned_unrefined','learned_refined',metric) for metric in ('chamfer_mm','volumetric_iou')]+[paired_interval(rows,'learned_no_proposal','learned_refined',metric) for metric in ('chamfer_mm','volumetric_iou')]
    environment={'python':platform.python_version(),'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),'numpy':np.__version__,'thread_limit':'OMP/OPENBLAS/MKL=1 unless inherited','note':'Inference runtime excludes CAD validation and benchmark-only metric computation; cold import time excluded.'}
    summary={'schema_version':1,'generated_utc':datetime.now(timezone.utc).isoformat(),'dataset':'procedural single-solid orthogonal grammar, held-out dimensions and scans','split':'train seeds 1000–1179; test seeds 9000–9047, no tuning on test','test_cases':args.count,'test_sha256':canonical_hash(cases),'model_sha256':hashlib.sha256((ROOT/'models/ranker.json').read_bytes()).hexdigest(),'model_manifest_sha256':canonical_hash(manifest),'methods':aggregates,'paired_comparisons':comparisons,'environment':environment,'total_seconds':time.perf_counter()-start,'limitations':['Synthetic in-distribution grammar test, not unconstrained reconstruction.','Chamfer is symmetric mean unsquared nearest-neighbor distance over two independent 7000-point surfaces. Sampling floor is measured separately.','Volume IoU is a 50000-point Monte Carlo estimate over union bounds.','External dimension error uses known generated extents, not fitted-surface distance. Thickness error conditional on family match and excludes solid blocks.','CAD validity and editability measured by actual kernel construction and 10% width edit for every successful candidate.','BBox baseline skips candidate ranking; runtime excludes shared preprocessing.','No upstream neural model benchmark was run; no superiority claim is supported.']}
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); (args.out/'test_manifest.json').write_text(json.dumps(cases,indent=2)+'\n')
    fields=['seed','method','truth_family','predicted_family','partial','chamfer_mm','sampling_floor_mm','volumetric_iou','external_dim_mae_mm','thickness_error_mm','family_correct','hole_count_correct','cad_valid','editable','runtime_seconds','validation_seconds','accepted','error']
    with (args.out/'cases.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); writer.writeheader(); writer.writerows(rows)
    table=['| Method | Chamfer mm ↓ | IoU ↑ | Extent MAE mm ↓ | Family | CAD valid | Editable | Inference s |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for method,a in aggregates.items():
        table.append(f'| {method} | {a["chamfer_mm_mean"]:.3f} | {a["volumetric_iou_mean"]:.3f} | {a["external_dim_mae_mm_mean"]:.3f} | {a["family_correct_rate"]:.1%} | {a["cad_valid_rate"]:.1%} | {a["editable_rate"]:.1%} | {a["runtime_seconds_mean"]:.3f} |')
    failures=sorted([r for r in rows if r['method']=='learned_refined' and r.get('error') is None],key=lambda r:r['volumetric_iou'])[:5]
    lines=['# Synthetic benchmark v1','',f'Actual local CPU run on {args.count} fixed held-out synthetic objects. No test tuning. Test bytes: `{summary["test_sha256"]}`.','']+table+['','## Measured paired effects','']
    for comp in comparisons:
        lo,hi=comp['bootstrap_95_percentile_ci']; lines.append(f'- {comp["comparison"]}, {comp["metric"]}: {comp["mean"]:+.4f}, exploratory paired bootstrap 95% interval [{lo:+.4f}, {hi:+.4f}].')
    lines+=['','## Failure cases','']
    for r in failures: lines.append(f'- Seed {r["seed"]}: {r["truth_family"]} → {r["predicted_family"]}, IoU {r["volumetric_iou"]:.3f}, Chamfer {r["chamfer_mm"]:.3f} mm, missing-side acquisition {r["partial"]}, {len(r["spec"].get("holes",[]))} predicted bores.')
    lines+=['','## Definitions and limitations','']+['- '+s for s in summary['limitations']]+['',f'Environment: `{json.dumps(environment,sort_keys=True)}`. Total benchmark time: {summary["total_seconds"]:.1f} s. Per-case values, failures, specs and manifest are saved alongside this report.','']
    (args.out/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(aggregates,indent=2))

if __name__=='__main__': main()
