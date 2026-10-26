#!/usr/bin/env python3
"""Train an inspectable pairwise evidence ranker on procedural engineering solids.

No pretrained model, paid service, executable model pickle, or test-set selection.
Reproduce from the repository root: python scripts/train.py
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ.setdefault(name,'1')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.spatial import cKDTree
from sklearn.linear_model import LogisticRegression
from objectdna.geometry import random_spec, simulate_scan, normalize_points, sample_surface, sdf, occupancy
from objectdna.inference import candidates, evidence_features, FEATURE_NAMES

TRAIN_SEEDS=range(1000,1180)
TEST_SEEDS=range(9000,9048)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def make_case(seed):
    rng=np.random.default_rng(seed)
    family=('block','bracket','enclosure')[seed%3]
    truth=random_spec(rng,family)
    noise=float(rng.uniform(.0005,.0035))
    partial=bool(seed%4==0)
    scan=simulate_scan(truth,seed+30000,n=1200,noise=noise,partial=partial,outliers=.01)
    cloud,dims,pose=normalize_points(scan,'mm')
    return truth,scan,cloud,dims,pose,dict(seed=seed,family=family,noise_fraction_diagonal=noise,partial=partial,truth=truth,scan_sha256=hashlib.sha256(scan.tobytes()).hexdigest())


def oracle_loss(spec,truth,translation,seed=0):
    """Unseen true-surface distance + volume mismatch, not an inference feature."""
    diag=np.linalg.norm([truth['parameters'][k] for k in ('width','depth','height')])
    true_surface=sample_surface(truth,1800,seed+210)
    candidate_surface=sample_surface(spec,1800,seed+211)+translation
    distance=(np.abs(sdf(true_surface-translation,spec)).mean()+np.abs(sdf(candidate_surface,truth)).mean())/(2*diag)
    dims=np.maximum([truth['parameters'][k] for k in ('width','depth','height')],np.array([spec['parameters'][k] for k in ('width','depth','height')])+translation)
    pts=np.random.default_rng(seed+212).uniform(0,dims,(6000,3))
    a=occupancy(pts,truth); b=occupancy(pts-translation,spec)
    iou=float((a&b).sum()/max((a|b).sum(),1))
    return float(distance+.06*(1-iou))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=180)
    parser.add_argument('--output',type=Path,default=ROOT/'models/ranker.json')
    args=parser.parse_args()
    if not 12<=args.count<=180: parser.error('--count must be 12–180; test seeds stay fixed.')
    started=time.perf_counter(); all_features=[]; groups=[]; cases=[]
    for idx,seed in enumerate(list(TRAIN_SEEDS)[:args.count]):
        truth,scan,cloud,dims,pose,record=make_case(seed)
        proposals=candidates(cloud,dims,use_learned_proposal=False); tree=cKDTree(cloud)
        features=np.array([evidence_features(cloud,p,tree) for p in proposals])
        loss=np.array([oracle_loss(p,truth,np.asarray(pose['translation']),seed) for p in proposals])
        offset=len(all_features); all_features.extend(features)
        groups.append((np.arange(len(features))+offset,loss))
        record.update(candidate_count=len(proposals),oracle_best_loss=float(loss.min()))
        cases.append(record)
        if idx%15==0: print(f'training data {idx+1}/{args.count}: {len(all_features)} candidates',flush=True)
    features=np.array(all_features); mean=features.mean(0); scale=features.std(0); scale[scale<1e-8]=1
    standardized=(features-mean)/scale
    rng=np.random.default_rng(157)
    pairs=[]; labels=[]; margins=[]
    for indices,loss in groups:
        # Use within-object preferences. Absolute shape IDs and dimensions never enter ranker.
        best=int(np.argmin(loss)); pool={(best,j) for j in range(len(loss)) if j!=best}
        for _ in range(80):
            i,j=rng.choice(len(indices),2,replace=False); pool.add((int(i),int(j)))
        for i,j in sorted(pool):
            difference=float(loss[i]-loss[j])
            if abs(difference)<.0004: continue
            pairs.append(standardized[indices[i]]-standardized[indices[j]])
            labels.append(int(difference>0)); margins.append(min(3.,abs(difference)/.01+.2))
            # Mirrored pair makes no-intercept training exactly symmetric.
            pairs.append(-pairs[-1]); labels.append(1-labels[-1]); margins.append(margins[-1])
    classifier=LogisticRegression(C=.12,fit_intercept=False,max_iter=2000,random_state=157)
    classifier.fit(np.asarray(pairs),np.asarray(labels),sample_weight=np.asarray(margins))
    weights=classifier.coef_[0]
    manifest={'schema_version':1,'generator':'ObjectDNA procedural three-family v1','train_cases':cases,'train_seed_range':[1000,1000+args.count-1],'reserved_test_seed_range':[9000,9047],'train_count':args.count,'candidate_count':len(features),'pair_count':len(pairs),'features':FEATURE_NAMES,'oracle':'true signed-surface discrepancy / diagonal + 0.06*(1 - Monte Carlo volume IoU), 1800 surface and 6000 volume samples','selection':'Fixed C=.12 and 0.0004 pair margin. No held-out test tuning.','software':{'python':platform.python_version(),'numpy':np.__version__},'training_seconds':time.perf_counter()-started}
    manifest['dataset_sha256']=canonical_hash(cases)
    model={'version':'pairwise-evidence-v1','features':FEATURE_NAMES,'mean':mean.tolist(),'scale':scale.tolist(),'weights':weights.tolist(),'training_manifest_sha256':canonical_hash(manifest),'description':'Linear pairwise logistic geometry-and-silhouette ranker; lower score is preferred. Scores are not calibrated probabilities.'}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(model,indent=2)+'\n')
    (args.output.parent/'training_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (args.output.parent/'MODEL_CARD.md').write_text(f'''# ObjectDNA evidence ranker v1

This CPU-trained, linear pairwise logistic ranker orders bounded CAD candidates using eleven scan agreement, reverse coverage, orthographic raster and complexity features. It is an original engineering experiment, not a claim of a new state of the art or an unconstrained CAD generator.

Training: {args.count} procedural solids, {len(features)} candidates, {len(pairs)} mirrored preferences. Shapes use seeds 1000–{999+args.count}; evaluation uses fixed disjoint seeds 9000–9047. Training labels use hidden synthetic solid geometry; inference does not have access to these labels. The generator shares the supported CAD grammar, so this is an in-distribution synthetic test.

Reproduce: `python scripts/train.py`. Model stores numeric coefficients in JSON and never runs model-supplied code. The JSON scores are ordering values, **not probabilities or calibrated confidence**. Training parameters were fixed before held-out evaluation.

Training data SHA-256: `{manifest['dataset_sha256']}`. Per-case seeds, parameters, scan hashes and settings are in `training_manifest.json`. Wall-clock training time on this machine: {manifest['training_seconds']:.1f} s.

Limitations: fixed families, orientation, noise and missing-side pattern; no material/function inference; no guaranteed hidden geometry; no independently verified real-part dimensional ground truth. Validate real capture performance separately. Geometry validation is a hard CadQuery check outside this trained ranker.
''')
    print(json.dumps({'model':str(args.output),'cases':args.count,'candidates':len(features),'pairs':len(pairs),'seconds':manifest['training_seconds'],'weights':dict(zip(FEATURE_NAMES,weights.tolist()))},indent=2))

if __name__=='__main__': main()
