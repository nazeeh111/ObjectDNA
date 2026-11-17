"""Project actual retained normalized points and actual CadQuery preview triangles.
Standard library only. Orthographic projection, common scale across before/after;
all retained source points are shown. This is not a physical accuracy study.
"""
from pathlib import Path
import json,html,hashlib
P=Path(__file__).resolve().parent
initial=json.loads((P/'initial-evidence.json').read_text());edited=json.loads((P/'edited-evidence.json').read_text())
assert len(initial['source_points'])==2392 and initial['source_points']==edited['source_points'];assert edited['spec']['parameters']['width']==90
project=lambda p:(.85*p[0]-.65*p[1],.35*p[0]+.25*p[1]-.95*p[2])
cloud=initial['source_points'];extent=[project(v) for v in edited['mesh']['vertices']+cloud];lo=[min(p[i] for p in extent) for i in (0,1)];hi=[max(p[i] for p in extent) for i in (0,1)]
def draw(mobile):
 w,h=(420,1130) if mobile else (1200,760);parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc">','<title id="title">ObjectDNA: evidence stays; design intent changes.</title>','<desc id="desc">Actual 2392 retained synthetic bracket points and fitted CAD at 80.075 mm width; a 90 mm width edit retains the points and becomes a user-specified hypothesis. Exported STEP and generated CadQuery reopen as one valid solid.</desc>','<style>text{font-family:Arial,Helvetica,sans-serif;fill:#e9ece8}.muted{fill:#b6c3bc}.accent{fill:#e7a86d}.mono{font-family:"Courier New",Courier,monospace}</style>',f'<rect width="{w}" height="{h}" fill="#192922"/>']
 def text(x,y,s,size=20,cls='',weight=400):parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" class="{cls}">{html.escape(s)}</text>')
 text(28 if mobile else 46,48,'ObjectDNA',25,weight=700)
 if mobile:
  text(28,98,'Evidence stays.',32,weight=700);text(28,136,'Design intent changes.',32,weight=700)
 else:text(46,111,'Evidence stays. Design intent changes.',48,weight=700)
 text(28 if mobile else 46,176 if mobile else 155,'Actual synthetic scan → editable bracket',17,'muted')
 for i,data in enumerate((initial,edited)):
  x,y,pw,ph=(28,212+i*340,364,260) if mobile else (46+i*568,210,538,330)
  scale=min((pw-30)/(hi[0]-lo[0]),(ph-45)/(hi[1]-lo[1]))
  def xy(p):a,b=project(p);return x+15+(a-lo[0])*scale,y+10+(b-lo[1])*scale
  mesh=data['mesh'];faces=sorted(mesh['faces'],key=lambda f:sum(mesh['vertices'][j][1]-mesh['vertices'][j][0]-mesh['vertices'][j][2] for j in f))
  for f in faces:
   pts=' '.join(f'{a:.3f},{b:.3f}' for a,b in [xy(mesh['vertices'][j]) for j in f]);parts.append(f'<polygon points="{pts}" fill="#466659" fill-opacity=".55" stroke="{chr(35)+("dfaa78" if i else "9eafa6")}" stroke-width=".8"/>')
  for p in cloud:
   a,b=xy(p);parts.append(f'<circle cx="{a:.3f}" cy="{b:.3f}" r=".75" fill="#d9e7df" fill-opacity=".65"/>')
  text(x,y+ph+22,'Fitted hypothesis' if not i else 'User-specified hypothesis',22,weight=700)
  width=data['spec']['parameters']['width'];text(x,y+ph+52,f'Width {width:.3f} mm' if not i else 'Width 90.000 mm',20,'accent' if i else 'muted')
  if mobile:text(x,y+ph+78,'Same 2,392 points. Different intent.' if i else '2,392 retained points; prealigned.',15,'muted')
  else:text(x,y+ph+82,'Point cloud unchanged. Acceptance is not inherited.' if i else 'Geometric fit within the bracket grammar.',18,'muted')
 if mobile:
  parts.append('<path d="M28 932H392" stroke="#667b6f"/>');text(28,971,'STEP reopened. Source rebuilt.',23,weight=700);text(28,1005,'One valid solid; 90 mm X extent.',18,'accent');text(28,1045,'An edit supplies intent, not a measurement.',16,'muted');text(28,1077,'No physical accuracy or fabrication claim.',16,'muted')
 else:
  parts.append('<path d="M46 675H1154" stroke="#667b6f"/>');text(46,714,'STEP reopened. Generated CadQuery rebuilt.',24,weight=700);text(46,744,'One valid solid; 90 mm X extent. Design intent is not a new scan measurement.',18,'muted')
 parts.append('</svg>');return '\n'.join(parts)+'\n'
for name,m in [('scan-to-edit',False),('scan-to-edit-mobile',True)]:(P/(name+'.svg')).write_text(draw(m))
print('Drew both real source/solid overlays; 2392 source circles per panel.')
