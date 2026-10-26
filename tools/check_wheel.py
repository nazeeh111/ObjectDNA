#!/usr/bin/env python3
"""Exercise a built wheel independently of the checkout, using installed dependencies."""

from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("wheel", type=Path)
args = p.parse_args()
with tempfile.TemporaryDirectory(prefix="objectdna-wheel-") as tmp:
    folder = Path(tmp)
    with zipfile.ZipFile(args.wheel) as archive:
        if archive.testzip():
            raise SystemExit("Wheel CRC validation failed")
        for name in archive.namelist():
            if name.startswith("/") or ".." in Path(name).parts:
                raise SystemExit("Unsafe wheel path")
        archive.extractall(folder)
    probe = folder / "probe.py"
    probe.write_text("""from pathlib import Path
import hashlib,json,re,tempfile
import objectdna
from objectdna.paths import asset_root
from objectdna.inference import load_ranker
from objectdna.proposal import load_proposal
from fastapi.testclient import TestClient
from objectdna.api import app
from objectdna.cad import build_shape
here=Path(__file__).resolve().parent
assert Path(objectdna.__file__).resolve().parent==here/'objectdna'
root=asset_root();assert root==here/'objectdna/assets'
manifest=json.loads((root/'ASSET_MANIFEST.json').read_text())
for name,sha in manifest.items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
assert load_ranker() and load_proposal()
c=TestClient(app); index=c.get('/'); assert index.status_code==200
for url in re.findall(r'(?:src|href)="(/assets/[^\\"]+)"',index.text):assert c.get(url).status_code==200,url
for url in ('/licenses/three-MIT.txt','/licenses/vite-LICENSE.md'):assert c.get(url).status_code==200,url
assert len(c.get('/api/samples').json()['samples'])==5
r=c.post('/api/reconstruct',json={'sample_id':'bracket','candidate_mode':'learned_compact'})
assert r.status_code==200,r.text
body=r.json();assert body['metrics']['valid'] and body['mesh']['faces']
assert body['provenance']['ranking']=='geometric'
s=body['spec'];s['parameters']['width']+=5
e=c.post('/api/edit',json={'id':body['id'],'spec':s});assert e.status_code==200,e.text
out=c.get('/api/export/'+e.json()['id']+'?format=step');assert out.status_code==200
import cadquery as cq
with tempfile.TemporaryDirectory() as temp:
 path=Path(temp)/'model.step';path.write_bytes(out.content)
 shape=cq.importers.importStep(str(path)).val()
 assert shape.isValid() and len(shape.Solids())==1
 assert abs(shape.BoundingBox().xlen-s['parameters']['width'])<1e-5
print(json.dumps({'status':'passed','bundled_assets':len(manifest),'models':2,'samples':5,'cad_edit_step_readback':True}))
""")
    subprocess.run([sys.executable, str(probe)], cwd=folder, check=True)
    subprocess.run(
        [sys.executable, "-m", "objectdna.cli", "--help"],
        cwd=folder,
        env={**__import__("os").environ, "PYTHONPATH": str(folder)},
        check=True,
        stdout=subprocess.DEVNULL,
    )
