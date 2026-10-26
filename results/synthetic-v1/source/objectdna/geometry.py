"""Analytic geometry used for fitting; exact export is independently built by CadQuery.

All templates are lower-corner anchored. Signed distances are in input units.
No unknown observation is converted into a measured dimension.
"""
from __future__ import annotations
import copy
import numpy as np
from scipy.spatial import cKDTree

FAMILIES = ('block', 'bracket', 'enclosure')


def boxes(spec):
    p = spec['parameters']; w,d,h,t = (p[k] for k in ('width','depth','height','thickness'))
    if spec['family'] == 'block': return [(np.zeros(3),np.array([w,d,h]))]
    b = [(np.zeros(3),np.array([w,d,t]))]
    if spec['family'] == 'bracket':
        return b+[(np.zeros(3),np.array([w,t,h]))]
    return b+[(np.zeros(3),np.array([w,t,h])),(np.array([0,d-t,0]),np.array([w,d,h])),(np.zeros(3),np.array([t,d,h])),(np.array([w-t,0,0]),np.array([w,d,h]))]


def box_sdf(points, lo, hi):
    q = np.abs(points-(lo+hi)/2)-(hi-lo)/2
    return np.linalg.norm(np.maximum(q,0),axis=1)+np.minimum(np.max(q,axis=1),0)


def sdf(points, spec):
    points = np.asarray(points)
    values = np.min([box_sdf(points,lo,hi) for lo,hi in boxes(spec)],axis=0)
    if spec['family'] == 'block':
        for hole in spec.get('holes',[]):
            radial = np.linalg.norm(points[:,:2]-[hole['x'],hole['y']],axis=1)-hole['radius']
            values = np.maximum(values,-radial)
    return values


def sample_surface(spec, n=2048, seed=0):
    """Area-weighted box/cylinder surfaces, remove internal union/difference faces."""
    rng = np.random.default_rng(seed); chunks=[]; weights=[]
    for lo,hi in boxes(spec):
        size=hi-lo
        for axis in range(3):
            area=float(np.prod(np.delete(size,axis)))
            for side in (0,1): chunks.append((lo,hi,axis,side)); weights.append(area)
    for hole in spec.get('holes',[]):
        chunks.append(hole); weights.append(2*np.pi*hole['radius']*spec['parameters']['height'])
    weights=np.asarray(weights); weights/=weights.sum()
    out=[]
    while sum(map(len,out))<n:
        count=max(n*2,512); choices=rng.choice(len(chunks),count,p=weights)
        pts=np.empty((count,3))
        for idx,ch in enumerate(chunks):
            mask=choices==idx; k=mask.sum()
            if isinstance(ch,dict):
                a=rng.uniform(0,2*np.pi,k)
                pts[mask]=np.column_stack([ch['x']+ch['radius']*np.cos(a),ch['y']+ch['radius']*np.sin(a),rng.uniform(0,spec['parameters']['height'],k)])
            else:
                lo,hi,axis,side=ch; p=rng.uniform(lo,hi,(k,3)); p[:,axis]=(lo if side==0 else hi)[axis]; pts[mask]=p
        keep=np.abs(sdf(pts,spec))<1e-6
        out.append(pts[keep])
    return np.concatenate(out)[:n]


def occupancy(points,spec): return sdf(points,spec)<=0


def volume_iou(a,b,n=16000,seed=0):
    dims=np.maximum([a['parameters'][k] for k in ('width','depth','height')],[b['parameters'][k] for k in ('width','depth','height')])
    pts=np.random.default_rng(seed).uniform(0,dims,(n,3))
    x,y=occupancy(pts,a),occupancy(pts,b)
    return float(np.sum(x&y)/max(np.sum(x|y),1))


def chamfer(a,b):
    """Symmetric mean *unsquared* nearest-neighbor distance, same units as input."""
    return float((cKDTree(a).query(b)[0].mean()+cKDTree(b).query(a)[0].mean())/2)


def random_spec(rng,family=None):
    family=family or rng.choice(FAMILIES)
    w=float(rng.uniform(30,110)); d=float(rng.uniform(24,85)); h=float(rng.uniform(16,65)); t=float(rng.uniform(2, min(w,d,h)*.22))
    spec={'family':family,'parameters':dict(width=w,depth=d,height=h,thickness=t),'holes':[]}
    if family=='block' and rng.random()<.75:
        radius=float(min(w,d)*rng.uniform(.07,.17))
        for x in ([w*.3,w*.7] if radius<min(w,d)*.12 else [w*.5]):
            spec['holes'].append(dict(x=float(x),y=d*.5,radius=radius))
    return spec


def simulate_scan(spec,seed,n=1600,noise=.0015,partial=False,outliers=.01):
    rng=np.random.default_rng(seed); pts=sample_surface(spec,n*3,seed)
    # Unknown surfaces are removed; no template labels are present in observations.
    if partial:
        # One physical side is occluded. Keep top and front-side evidence.
        dims=np.array([spec['parameters'][k] for k in ('width','depth','height')])
        pts=pts[(pts[:,2]>dims[2]*.08)|(pts[:,1]>dims[1]*.75)]
    pts=pts[rng.choice(len(pts),n,replace=len(pts)<n)]
    diag=np.linalg.norm([spec['parameters'][k] for k in ('width','depth','height')])
    pts+=rng.normal(0,diag*noise,pts.shape)
    k=int(n*outliers)
    if k: pts[:k]=rng.uniform(pts.min(0),pts.max(0),(k,3))
    return pts


def validate_points(points,max_points=200000):
    a=np.asarray(points,dtype=float)
    if a.ndim!=2 or a.shape[1]!=3 or not 80<=len(a)<=max_points:
        raise ValueError('Provide 80–200,000 XYZ points with three coordinates each.')
    if not np.isfinite(a).all(): raise ValueError('Point coordinates must be finite.')
    if np.max(np.abs(a))>1e9: raise ValueError('Coordinates are too large. Translate or rescale the scan.')
    if np.linalg.matrix_rank(a-a.mean(0),tol=max(np.ptp(a,axis=0))*.0001)<3:
        raise ValueError('The scan is planar or degenerate; three-dimensional evidence is required.')
    return a


def normalize_points(points,units='mm',reference_extent_mm=None,align=False):
    """Robust denoising and optional PCA pose. PCA is an initial pose, never a guarantee."""
    a=validate_points(points)
    if units not in ('mm','m','unknown'): raise ValueError('Units must be mm, m, or unknown.')
    if units=='m': a=a*1000
    if len(a)>6000: a=a[np.random.default_rng(0).choice(len(a),6000,replace=False)]
    distances=cKDTree(a).query(a,k=8)[0][:,1:].mean(1)
    median=np.median(distances); mad=np.median(np.abs(distances-median))
    keep=distances<median+max(6*mad,median*1.5)
    a=a[keep]
    rotation=np.eye(3); center=a.mean(0)
    if align:
        _,rotation=np.linalg.eigh(np.cov((a-center).T)); rotation=rotation[:,::-1]
        if np.linalg.det(rotation)<0: rotation[:,2]*=-1
        a=(a-center)@rotation
    lo=np.quantile(a,.004,axis=0); hi=np.quantile(a,.996,axis=0)
    a-=lo; extent=hi-lo
    if min(extent)<max(extent)*.003: raise ValueError('Insufficient thickness evidence in this scan.')
    scale=1.
    if reference_extent_mm is not None:
        if not np.isfinite(reference_extent_mm) or not .1<=reference_extent_mm<=100000:
            raise ValueError('Reference maximum extent must be 0.1–100,000 mm.')
        scale=float(reference_extent_mm/max(extent)); a*=scale; extent*=scale
    elif units=='unknown':
        scale=100/max(extent); a*=scale; extent*=scale
    return a,extent,{'rotation':rotation.tolist(),'translation':lo.tolist(),'pca_center':center.tolist() if align else None,'scale':scale,'pca_alignment':align,'input_units':units,'calibrated':units!='unknown' or reference_extent_mm is not None,'reference_extent_mm':reference_extent_mm,'removed_points':int((~keep).sum())}
