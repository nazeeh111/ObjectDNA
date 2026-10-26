"""Constrained candidates + learned evidence ranking + analytic SDF refinement.

The grammar is deliberately bounded. A low residual is not proof of hidden geometry.
Learned weights score observable geometric evidence; they do not invent dimensions.
"""
from __future__ import annotations
from pathlib import Path
import copy
import json
import time
import numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import least_squares
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d, binary_dilation
from .geometry import sdf, sample_surface, normalize_points

ROOT=Path(__file__).resolve().parents[1]
FEATURE_NAMES=['observed_mean','observed_p90','observed_rms','reverse_mean','reverse_p90','silhouette_xy','silhouette_xz','silhouette_yz','unexplained_fraction','unsupported_fraction','complexity']


def detect_holes(points,dims):
    """Detect cylindrical wall evidence, never infer a bore from an empty patch alone."""
    from scipy.cluster.hierarchy import fclusterdata
    diag=np.linalg.norm(dims); margin=diag*.018
    mask=(points[:,2]>margin)&(points[:,2]<dims[2]-margin)&(points[:,0]>margin)&(points[:,0]<dims[0]-margin)&(points[:,1]>margin)&(points[:,1]<dims[1]-margin)
    pts=points[mask]
    if len(pts)<25: return []
    if len(pts)>1500: pts=pts[np.linspace(0,len(pts)-1,1500,dtype=int)]
    labels=fclusterdata(pts[:,:2],diag*.05,criterion='distance',method='single')
    holes=[]
    for label in np.unique(labels):
        cloud=pts[labels==label]
        if len(cloud)<25 or np.ptp(cloud[:,2])<dims[2]*.3: continue
        xy=cloud[:,:2]; A=np.column_stack([2*xy,np.ones(len(xy))]); b=np.sum(xy**2,axis=1)
        x,y,c=np.linalg.lstsq(A,b,rcond=None)[0]; radius=np.sqrt(max(0,c+x*x+y*y))
        radial=np.linalg.norm(xy-[x,y],axis=1)
        angles=np.arctan2(xy[:,1]-y,xy[:,0]-x)
        bins=np.histogram(angles,bins=12,range=(-np.pi,np.pi))[0]
        if radius>diag*.015 and radius<min(dims[:2])*.35 and np.std(radial)<radius*.12 and (bins>0).sum()>=9 and radius<x<dims[0]-radius and radius<y<dims[1]-radius:
            holes.append(dict(x=float(x),y=float(y),radius=float(radius)))
    return holes[:8]


def candidates(points,dims,use_learned_proposal=True,candidate_mode="dense"):
    if candidate_mode not in ("dense","learned_compact"): raise ValueError("Candidate mode must be dense or learned_compact.")
    smallest=float(min(dims)); ts=list(smallest*np.array([.035,.06,.10,.16,.23,.32]))
    for axis in (range(3) if candidate_mode=="dense" else []):
        hist,edges=np.histogram(points[:,axis],bins=128,range=(0,dims[axis]))
        smooth=gaussian_filter1d(hist.astype(float),1)
        peaks,_=find_peaks(smooth,prominence=max(3,smooth.max()*.045),distance=3)
        for peak in peaks:
            val=(edges[peak]+edges[peak+1])/2
            for t in (val,dims[axis]-val):
                if smallest*.02<t<smallest*.4: ts.append(float(t))
    ts=sorted(set(round(t,3) for t in ts))[:20]
    holes=detect_holes(points,dims)
    out=[]
    from .proposal import predict_thickness, load_proposal
    proposal_model=load_proposal() if use_learned_proposal else None
    if candidate_mode=='learned_compact' and proposal_model is None: raise ValueError('Compact mode requires the trained proposal model. Restore models/proposal.json or select dense mode.')
    for family in ('block','bracket','enclosure'):
        family_ts=[smallest*.1] if family=='block' else ts.copy()
        predicted=predict_thickness(points,dims,family,proposal_model) if proposal_model else None
        if candidate_mode=='learned_compact' and family!='block':
            family_ts=[float(np.clip(predicted*ratio,smallest*.02,smallest*.40)) for ratio in (.85,1.,1.15)]
        elif predicted is not None: family_ts.append(predicted)
        for t in family_ts:
            if family=='enclosure' and 2*t>=min(dims[:2]): continue
            if family=='bracket' and t>=min(dims[1:]): continue
            p=dict(zip(('width','depth','height'),map(float,dims))); p['thickness']=t
            out.append(dict(family=family,parameters=p,holes=[]))
            if family=='block' and holes: out.append(dict(family=family,parameters=p.copy(),holes=holes))
    return out


def silhouette_mismatch(points,surface,dims,axes,resolution=32):
    # Rasterized orthographic silhouette feedback. Dilate sparse pixels equally.
    def render(p):
        ij=np.floor(p[:,axes]/dims[list(axes)]*(resolution-1)).astype(int)
        ij=np.clip(ij,0,resolution-1); image=np.zeros((resolution,resolution),bool); image[ij[:,0],ij[:,1]]=True
        return binary_dilation(image,iterations=1)
    a,b=render(points),render(surface)
    return 1-float((a&b).sum()/max((a|b).sum(),1))


def evidence_features(points,spec,tree=None):
    dims=np.array([spec['parameters'][k] for k in ('width','depth','height')]); diag=np.linalg.norm(dims)
    surface=sample_surface(spec,1400,31)
    obs=np.abs(sdf(points,spec))/diag
    rev=(tree or cKDTree(points)).query(surface)[0]/diag
    return np.array([obs.mean(),np.quantile(obs,.9),np.sqrt(np.mean(obs**2)),rev.mean(),np.quantile(rev,.9),*[silhouette_mismatch(points,surface,dims,axes) for axes in ((0,1),(0,2),(1,2))],np.mean(obs>.012),np.mean(rev>.025),(1 if spec['family']=='block' else 2 if spec['family']=='bracket' else 5)+len(spec.get('holes',[]))],float)


def geometric_score(features):
    return float(features[0]+features[3])


def learned_score(features,model):
    x=(features-np.array(model['mean']))/np.array(model['scale'])
    # Lower score is preferred. Pairwise logistic weights; transparent JSON only.
    return float(x@np.array(model['weights']))


def load_ranker(path=None):
    path=Path(path) if path else ROOT/'models/ranker.json'
    if not path.exists(): return None
    model=json.loads(path.read_text())
    if model['features']!=FEATURE_NAMES: raise ValueError('Ranker feature version does not match this pipeline.')
    return model


def refine_spec(points,spec):
    result=copy.deepcopy(spec); keys=['width','depth','height']+([] if spec['family']=='block' else ['thickness'])
    p=spec['parameters']; x0=np.array([p[k] for k in keys]); diag=np.linalg.norm(x0[:3])
    lower=x0.copy(); upper=x0.copy(); lower[:3]*=.96; upper[:3]*=1.04
    if len(keys)==4:
        lower[3]=max(.02,x0[3]*.45); upper[3]=min(min(x0[:3])*.45,x0[3]*1.8)
    if np.any(lower>=upper): return result
    cloud=points[np.linspace(0,len(points)-1,min(1800,len(points)),dtype=int)]
    def residual(x):
        sp=copy.deepcopy(spec); sp['parameters'].update(dict(zip(keys,map(float,x))))
        return sdf(cloud,sp)/diag
    fit=least_squares(residual,x0,bounds=(lower,upper),loss='soft_l1',f_scale=.003,max_nfev=45)
    result['parameters'].update(dict(zip(keys,map(float,fit.x))))
    # Fit observed circles already estimated from all points; do not optimize toward absent surfaces.
    return result


def reconstruct(points,units='mm',reference_extent_mm=None,ranking='learned',refine=True,align=False,use_learned_proposal=True,candidate_mode="dense"):
    started=time.perf_counter()
    if ranking not in ('learned','geometric'): raise ValueError('Ranking must be learned or geometric.')
    cloud,dims,pose=normalize_points(points,units,reference_extent_mm,align)
    model=load_ranker() if ranking=='learned' else None
    proposals=candidates(cloud,dims,use_learned_proposal,candidate_mode); tree=cKDTree(cloud)
    rows=[]
    for spec in proposals:
        features=evidence_features(cloud,spec,tree)
        score=learned_score(features,model) if model else geometric_score(features)
        rows.append(dict(spec=spec,features=features,score=score))
    rows.sort(key=lambda r:r['score'])
    # Refine strongest candidate from each family and rerank the exact same evidence.
    if refine:
        for family in ('block','bracket','enclosure'):
            top=next(r for r in rows if r['spec']['family']==family)
            sp=refine_spec(cloud,top['spec']); f=evidence_features(cloud,sp,tree)
            rows.append(dict(spec=sp,features=f,score=learned_score(f,model) if model else geometric_score(f)))
        rows.sort(key=lambda r:r['score'])
    best=rows[0]; spec=best['spec']; diag=np.linalg.norm([spec['parameters'][k] for k in ('width','depth','height')])
    obs=np.abs(sdf(cloud,spec)); surface=sample_surface(spec,5000,77)
    reverse=cKDTree(cloud).query(surface)[0]
    warnings=['Single-solid reconstruction within a limited grammar; no material, load capacity, fit or mechanical function is established.']
    if ranking=='learned' and model is None: warnings.append('Ranker weights unavailable; geometric baseline used.')
    if not pose['calibrated']: warnings.append('Scale is unknown. Preview uses a normalized 100-unit maximum extent; metric CAD export is blocked until calibrated.')
    if align: warnings.append('PCA pose is approximate; symmetric, partial or non-orthogonal parts may require prealignment.')
    supported=float(np.mean(obs<diag*.012)); coverage=float(np.mean(reverse<diag*.025))
    accepted=supported>=.88 and coverage>=.65
    if not accepted: warnings.append('Low evidence support: this candidate is a hypothesis. Inspect residuals and unsupported surfaces before use.')
    uncertainty=[{'feature':'External extents','status':'observed','detail':'Robust scan bounds fitted to observed surface evidence; not an independent dimensional measurement.'},{'feature':'Wall thickness / feature family','status':'inferred','detail':'Selected within the bounded CAD grammar; verify with a physical measurement.'},{'feature':'Hidden surfaces and internal features','status':'unknown','detail':'Unseen geometry cannot be recovered from these points. Candidate completes the chosen template.'},{'feature':'Absolute scale','status':'calibrated' if pose['calibrated'] else 'unknown','detail':'Declared input units or maximum-extent reference used.' if pose['calibrated'] else 'No absolute length evidence was supplied.'}]
    if spec.get('holes'): uncertainty.append({'feature':'Through-bores','status':'inferred','detail':'Cylindrical wall evidence detected; through-depth completion assumes the block grammar. Inspect both openings.'})
    return {'spec':spec,'source_points':cloud.tolist(),'metrics':{'observed_rmse_mm':float(np.sqrt(np.mean(obs**2))) if pose['calibrated'] else None,'chamfer_mm':float((obs.mean()+reverse.mean())/2) if pose['calibrated'] else None,'observed_support':supported,'surface_coverage':coverage,'accepted':accepted,'volumetric_iou':None,'dimensional_error_mm':None},'uncertainty':uncertainty,'candidates':[{'family':r['spec']['family'],'score':float(r['score']),'spec':r['spec']} for r in rows[:6]],'warnings':warnings,'provenance':{'transform':pose,'ranking':'learned' if model else 'geometric','ranker_version':model.get('version') if model else None,'refined':refine,'learned_proposal':bool(use_learned_proposal and (ROOT/'models/proposal.json').exists()),'candidate_mode':candidate_mode,'candidate_count':len(proposals),'scope':'three-family orthogonal single-solid grammar'},'runtime_seconds':time.perf_counter()-started,'units':'mm' if pose['calibrated'] else 'relative','residuals':obs.tolist()}
