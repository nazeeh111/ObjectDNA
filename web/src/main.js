import './style.css';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const icon = (name, size = 18) => {
  const paths = {
    upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>',
    cube: '<path d="m12 3 9 5v8l-9 5-9-5V8Zm0 10v8M3 8l9 5 9-5M7 5l10 6"/>',
    scan: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M7 8h.01M12 7h.01M17 9h.01M8 13h.01M13 12h.01M17 16h.01M11 17h.01"/>',
    arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    reset: '<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6"/>',
    fit: '<path d="M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6M9 9h6v6H9Z"/>',
    layers: '<path d="m12 3 10 5-10 5L2 8Zm-9 9 9 5 9-5M3 17l9 5 9-5"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
  };
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.cube}</svg>`;
};

const $ = (selector) => document.querySelector(selector);
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = (value, digits = 2) => Number.isFinite(Number(value)) && value !== null && value !== undefined ? Number(value).toLocaleString('en-US', {maximumFractionDigits: digits}) : '—';
const label = value => String(value || '').replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());

$('#app').innerHTML = `
<header class="topbar">
  <a class="brand" href="/" aria-label="ObjectDNA home"><img src="/logo.svg" alt=""/><span>Object<span class="brand-light">DNA</span></span><span class="version">RESEARCH / 0.1</span></a>
  <div class="top-navigation"><span class="top-active">Workbench</span><a href="/docs" target="_blank" rel="noopener">API reference ${icon('arrow',14)}</a></div>
  <div class="local-state"><span class="status-dot"></span><span id="connection">Connecting locally</span></div>
</header>
<div class="projectbar">
  <div class="project-heading"><span class="eyebrow">REVERSE ENGINEERING</span><h1 id="project-title">New reconstruction</h1><p id="project-source" class="source-caption">Prealigned scans · three supported construction families</p></div>
  <div class="project-meta"><span id="project-tag" class="tag">POINT CLOUD → PARAMETRIC CAD</span><button class="button export-button" id="export-open" disabled>${icon('download')} Export model ${icon('chevron',13)}</button></div>
</div>
<div id="error-banner" class="error-banner" role="alert" hidden><div>${icon('info')}<span id="error-message"></span></div><button id="error-close" class="icon-button" aria-label="Dismiss error">${icon('close')}</button></div>
<main class="workbench">
  <aside class="left-panel panel">
    <section class="panel-section source-section">
      <div class="section-heading"><h2>Source geometry</h2><span class="section-number">01</span></div>
      <label class="dropzone" id="dropzone" for="file-input">${icon('upload',23)}<strong>Import a scan</strong><span>Drop a point cloud or browse</span><small>XYZ · PLY · PCD · STL · OBJ · NPY</small><input type="file" id="file-input" accept=".xyz,.txt,.csv,.pts,.ply,.pcd,.stl,.obj,.npy"/></label>
      <div class="scale-fields"><label>Import units<select id="units"><option value="unknown">Unknown / relative</option><option value="mm">Millimeters (mm)</option><option value="m">Meters (m)</option></select></label><label>Reference extent <span class="hint">optional</span><div class="input-with-unit"><input id="reference" type="number" min="0.01" max="100000" step="any" placeholder="Longest object extent"/><span>mm</span></div></label></div>
      <label class="align-check"><input type="checkbox" id="align-pca"/> Estimate object axes with PCA</label><p class="field-note">PCA estimates the main axes. Prealigned scans are preferred.</p>
      <p class="field-note">A reference sets the longest bounding-box extent. Scale is never inferred from appearance.</p><button type="button" id="apply-import-settings" class="import-settings-button" disabled>Apply import settings ${icon('arrow',13)}</button><p id="import-settings-note" class="field-note" aria-live="polite">Settings apply to uploaded files. Samples use their supplied units.</p>
    </section>
    <section class="panel-section samples-section">
      <div class="section-heading"><h2>Sample library</h2><span id="sample-count" class="small-count">—</span></div>
      <div id="samples" class="samples"><span class="muted">Loading available scans…</span></div>
    </section>
    <section class="panel-section feature-section">
      <div class="section-heading"><h2>Feature tree</h2><span class="section-number">02</span></div>
      <div id="feature-tree" class="feature-tree"><p class="muted">A reconstructed model will appear here.</p></div>
      <p class="field-note feature-note">An editable construction hypothesis. Hidden geometry requires your review.</p>
    </section>
    <div class="sidebar-footer"><span class="tiny-dna">O∕D</span><div>Local by design<small>Your uploads stay on this machine.</small></div></div>
  </aside>
  <section class="viewport-column">
    <div class="viewport" id="viewport">
      <div class="viewport-top"><span class="viewport-label"><span class="status-dot teal"></span> <span id="viewport-status">WAITING FOR GEOMETRY</span></span><div class="view-tabs" role="group" aria-label="Geometry display"><button data-view="overlay" class="active" aria-pressed="true">Overlay</button><button data-view="cad" aria-pressed="false">CAD</button><button data-view="source" aria-pressed="false">Source</button></div></div>
      <div class="canvas-wrap" id="canvas-wrap" role="group" tabindex="0" aria-label="Interactive 3D geometry" aria-describedby="viewer-help"></div><p id="viewer-help" class="keyboard-help">Keyboard: arrows orbit · + / − zoom · F fit · 1 iso · 2 top · 3 front</p>
      <div class="empty-state" id="empty-state">${icon('scan',45)}<h2>Every surface has a story.</h2><p>Import measured geometry or choose a sample<br/>to recover its editable construction.</p></div>
      <div class="viewport-title" id="viewport-title" hidden><span class="eyebrow">RECONSTRUCTION</span><h2 id="model-family">—</h2><p id="model-subtitle">Editable solid · millimeters</p><div id="support-status" class="support-status" hidden></div><div class="viewport-shortcuts"><button id="jump-parameters">Edit parameters ${icon('arrow',12)}</button><button id="jump-evidence">Review evidence ${icon('arrow',12)}</button></div></div>
      <div class="legend"><span><i class="legend-dot cad-dot"></i> CAD surface</span><span><i class="legend-dot source-dot"></i> Source points</span></div>
      <div class="view-tools"><button class="icon-button" id="fit-view" title="Fit geometry to view" aria-label="Fit geometry to view">${icon('fit')}</button><button class="view-preset" data-camera="top" aria-pressed="false">Top</button><button class="view-preset" data-camera="front" aria-pressed="false">Front</button><button class="view-preset active" data-camera="iso" aria-pressed="true">Iso</button></div>
      <div class="orbit-note">Drag to orbit <span>·</span> Scroll to zoom <span>·</span> Right-drag to pan</div>
      <div class="axis-widget" role="img" aria-label="Axes"><span class="axis-x">X</span><span class="axis-y">Y</span><span class="axis-z">Z</span><i class="axis-line line-x"></i><i class="axis-line line-y"></i><i class="axis-line line-z"></i><i class="axis-center"></i></div>
      <div class="busy-overlay" id="busy-overlay" role="status" aria-live="polite" hidden><span class="spinner"></span><strong id="busy-title">Reconstructing geometry</strong><span>Fitting candidates and checking the solid…</span></div>
    </div>
    <div class="evidence-strip">
      <div class="evidence-intro"><span class="eyebrow">GEOMETRIC EVIDENCE</span><h2>Check the fit.</h2><p>Measured against the source.</p></div>
      <div class="metric"><span title="Root mean squared template residual; approximate near intersecting cuts and overlaps.">Fit residual (RMS) ${icon('info',13)}</span><strong id="metric-rmse">—<small>mm</small></strong><p>Approximate template fit residual</p></div>
      <div class="metric"><span>Surface discrepancy</span><strong id="metric-chamfer">—<small>mm</small></strong><p>Analytic observed + sampled reverse distance</p></div>
      <div class="metric"><span>Solid validity</span><strong id="metric-valid">—</strong><p id="metric-valid-note">Kernel check pending</p></div>
      <div class="metric runtime-metric"><span>Inference time</span><strong id="metric-runtime">—<small>s</small></strong><p>Measured on this machine</p></div>
    </div>
    <div class="bottom-line"><span id="points-count">NO SOURCE LOADED</span><span id="model-volume">CAD KERNEL / OPENCASCADE</span></div>
  </section>
  <aside class="right-panel panel">
    <section class="panel-section dimensions-section" id="parameter-section" tabindex="-1">
      <div class="section-heading"><h2>Parameters</h2><span class="tag quiet" id="dimension-units">mm</span></div>
      <div class="parameter-intro"><span class="parameter-symbol">ƒ</span><p>Change a dimension.<br/><strong>Rebuild the actual solid.</strong></p></div>
      <form id="dimension-form"><div id="dimension-fields" class="dimension-fields"><p class="muted">Reconstruct geometry to edit its dimensions.</p></div><div class="dimension-actions"><button type="submit" id="apply-edit" class="button primary" disabled>Apply dimensions ${icon('arrow',15)}</button><button type="button" id="reset-edit" class="icon-button" title="Restore reconstructed dimensions" aria-label="Restore reconstructed dimensions" disabled>${icon('reset')}</button></div></form>
      <div id="edit-status" class="edit-status" aria-live="polite">Dimensions rebuild after a change.</div>
    </section>
    <section class="panel-section uncertainty-section" id="evidence-section" tabindex="-1">
      <div class="section-heading"><h2>What is known</h2><span class="section-number">03</span></div>
      <div id="uncertainty" class="uncertainty-list"><p class="muted">Evidence and assumptions appear after reconstruction.</p></div>
    </section>
    <section class="panel-section candidates-section">
      <div class="section-heading"><h2>Candidate ranking</h2></div>
      <div class="ranking-controls"><label class="sr-only" for="ranking">Candidate ranking method</label><select id="ranking"><option value="learned">Experimental learned score</option><option value="geometric" selected>Geometric score</option></select></div><div class="ranking-controls"><label class="control-label" for="candidate-mode">Candidate generation</label><select id="candidate-mode"><option value="dense">Dense + learned proposal</option><option value="learned_compact">Compact learned proposal</option></select></div>
      <div id="candidates" class="candidates"><p class="muted">No candidates yet.</p></div>
      <p class="field-note">Scores compare hypotheses; they are not calibrated confidence probabilities.</p>
    </section>
    <section class="panel-section provenance-section"><div class="section-heading"><h2>Source record</h2></div><div id="provenance" class="provenance"><p class="muted">No source loaded.</p></div><div id="warnings" class="warnings"></div></section>
  </aside>
</main>
<dialog id="export-dialog" aria-labelledby="export-heading" aria-describedby="export-note"><div class="dialog-heading"><div><span class="eyebrow">TAKE IT FURTHER</span><h2 id="export-heading">Export your reconstruction.</h2></div><button class="icon-button" id="export-close" aria-label="Close export dialog">${icon('close')}</button></div><p>STEP preserves analytic geometry. Keep the CadQuery script or project JSON for editable parameters.</p><div class="export-options"><button data-export="step"><span class="file-format">STEP</span><div><strong>Engineering solid</strong><small>Analytic CAD interchange · .step</small></div>${icon('download')}</button><button data-export="stl"><span class="file-format">STL</span><div><strong>Surface mesh</strong><small>Tessellated geometry · .stl</small></div>${icon('download')}</button><button data-export="py"><span class="file-format">PY</span><div><strong>CadQuery source</strong><small>Editable construction script · .py</small></div>${icon('download')}</button><button data-export="json"><span class="file-format">JSON</span><div><strong>Project record</strong><small>Parameters and reconstruction evidence · .json</small></div>${icon('download')}</button></div><p id="export-note" class="dialog-note" role="status" aria-live="polite">Review inferred features before manufacturing.</p></dialog>
`;

let result = null;
let originalSpec = null;
let sampleList = [];
let selectedSample = null;
let lastFile = null;
let busy = false;
let displayMode = 'overlay';
let editTimer;
let editSequence = 0;
let lastRequest = null;
let exporting = false;
const state = { renderer: null, scene: null, camera: null, controls: null, model: null, cloud: null, dimensions: null, grid: null, center: new THREE.Vector3(), size: 100 };

function showError(message) {
  $('#error-message').textContent = message;
  $('#error-banner').hidden = false;
}
function clearError() { $('#error-banner').hidden = true; }
function setBusy(value, title = 'Reconstructing geometry') {
  busy = value;
  $('#busy-overlay').hidden = !value;
  $('#busy-title').textContent = title;
  $('#viewport-status').textContent = value ? 'PROCESSING GEOMETRY' : (result ? result.metrics?.accepted === false ? 'HYPOTHESIS / REVIEW REQUIRED' : 'LOCAL RECONSTRUCTION' : 'WAITING FOR GEOMETRY');
  $('#export-open').disabled = value || !result;
  $('#apply-edit').disabled = value || !result;
  $('#reset-edit').disabled = value || !result;
  document.querySelectorAll('.sample-button').forEach(el => el.disabled = value);
  $('#file-input').disabled = value;
  $('#ranking').disabled = value;
  $('#candidate-mode').disabled = value;
  $('#apply-import-settings').disabled=value||!lastFile;
  $('#viewport').setAttribute('aria-busy',String(value));
  document.querySelectorAll('#dimension-form input').forEach(input=>input.disabled=value);
}
async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail;
    try { const body = await response.json(); detail = body.detail || body.error; } catch {}
    if (typeof detail !== 'string') detail = detail ? JSON.stringify(detail) : `${response.status} ${response.statusText}`;
    throw new Error(detail);
  }
  return response.json();
}

function init3D() {
  const target = $('#canvas-wrap');
  try {
    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true, preserveDrawingBuffer: true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0xf0f0e9, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    target.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1, 0.01, 100000);
    camera.up.set(0, 0, 1);
    camera.position.set(150, -180, 140);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x66746b, 2.9));
    const key = new THREE.DirectionalLight(0xffffff, 3.5); key.position.set(100, -100, 180); scene.add(key);
    const fill = new THREE.DirectionalLight(0xf9d0ac, 1.4); fill.position.set(-100, 100, 50); scene.add(fill);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.08; controls.maxPolarAngle = Math.PI * 0.93;
    Object.assign(state, {renderer, scene, camera, controls});
    const resize = () => { const {width, height} = target.getBoundingClientRect(); renderer.setSize(width, height); camera.aspect = width / Math.max(height, 1); camera.updateProjectionMatrix(); if(state.model || state.cloud) fitCamera(); };
    new ResizeObserver(resize).observe(target); resize();
    renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); updateAxisWidget(); });
  } catch (error) { showError(`The 3D viewer could not initialize. Enable WebGL in your browser. ${error.message}`); }
}
function dispose(object) {
  if (!object) return;
  state.scene.remove(object);
  object.traverse(child => { child.geometry?.dispose(); if (Array.isArray(child.material)) child.material.forEach(m => m.dispose()); else child.material?.dispose(); });
}
function applyDisplay() {
  if (state.model) state.model.visible = displayMode !== 'source';
  if (state.cloud) state.cloud.visible = displayMode !== 'cad';
  if (state.dimensions) state.dimensions.visible = displayMode !== 'source';
  $('.legend').classList.toggle('source-only', displayMode === 'source');
  $('.legend').classList.toggle('cad-only', displayMode === 'cad');
}
function fitCamera(preset = 'iso') {
  if (!state.camera) return;
  const direction = {iso: [1.2, 1.5, 1.05], top: [0, 0.001, 2], front: [0, 2, 0.02]}[preset] || [1.2,1.5,1.05];
  const vec = new THREE.Vector3(...direction).normalize();
  const aspect = state.camera.aspect;
  const distance = state.size / (2 * Math.tan(THREE.MathUtils.degToRad(state.camera.fov / 2))) * (aspect < 1 ? 1.35 / aspect : 1.65);
  state.camera.position.copy(state.center).addScaledVector(vec, distance);
  state.controls.target.copy(state.center);
  state.camera.near = Math.max(0.001, state.size / 10000); state.camera.far = state.size * 100;
  state.camera.updateProjectionMatrix(); state.controls.update();
  document.querySelectorAll('[data-camera]').forEach(b => {const selected=b.dataset.camera===preset;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected));});
}
function updateAxisWidget() {
  if (!state.camera) return;
  const inverse=state.camera.quaternion.clone().invert();
  for (const [axis,vector] of [['x',[1,0,0]],['y',[0,1,0]],['z',[0,0,1]]]) {
    const projected=new THREE.Vector3(...vector).applyQuaternion(inverse);
    const length=Math.hypot(projected.x,projected.y)*22;
    const text=$(`.axis-${axis}`),line=$(`.line-${axis}`);
    text.style.left=`${24+projected.x*28}px`;text.style.top=`${24-projected.y*28}px`;
    text.style.opacity=projected.z>0?.55:1;
    line.style.width=`${length}px`;line.style.transform=`rotate(${Math.atan2(-projected.y,projected.x)}rad)`;
    line.style.opacity=projected.z>0?.45:.8;
  }
}
function makeDimension(a, b, text) {
  const group = new THREE.Group();
  const material = new THREE.LineBasicMaterial({color: 0xd2683e, transparent: true, opacity: 0.75});
  const s = state.size;
  const dir = new THREE.Vector3().subVectors(b,a).normalize();
  const cross = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0,0,1)).normalize().multiplyScalar(s * 0.025);
  const line = (p,q) => group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([p,q]), material));
  line(a,b); line(a.clone().sub(cross),a.clone().add(cross)); line(b.clone().sub(cross),b.clone().add(cross));
  const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 96;
  const ctx = canvas.getContext('2d'); ctx.font = '500 40px monospace';
  const width = Math.min(500, ctx.measureText(text).width + 40);
  ctx.fillStyle = '#f3f1eb'; ctx.fillRect(256-width/2, 10, width, 72);
  ctx.fillStyle = '#9d4c2b'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, 256, 48);
  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map:texture, transparent:true, depthTest:false}));
  sprite.position.copy(a).add(b).multiplyScalar(0.5); sprite.scale.set(s*.38, s*.071,1); group.add(sprite);
  return group;
}
function renderGeometry(data, keepCamera = false) {
  if (!state.scene) return;
  ['model','cloud','dimensions','grid'].forEach(k => { dispose(state[k]); state[k] = null; });
  const mesh = data.mesh;
  const all = [];
  if (mesh?.vertices?.length && mesh?.faces?.length) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(mesh.vertices.flat(), 3));
    geometry.setIndex(mesh.faces.flat()); geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({color: 0x749d9a, metalness:0.18, roughness:0.5, side:THREE.DoubleSide, polygonOffset:true, polygonOffsetFactor:1, polygonOffsetUnits:1});
    const solid = new THREE.Mesh(geometry, material);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 25), new THREE.LineBasicMaterial({color:0x244f50, transparent:true,opacity:0.85}));
    state.model = new THREE.Group(); state.model.add(solid,edges); state.scene.add(state.model);
    all.push(...mesh.vertices);
  }
  if (data.source_points?.length) {
    const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position',new THREE.Float32BufferAttribute(data.source_points.flat(),3));
    state.cloud = new THREE.Points(geometry,new THREE.PointsMaterial({color:0xdb653b,size:2.1,sizeAttenuation:false,transparent:true,opacity:0.63,depthTest:true}));
    state.scene.add(state.cloud); all.push(...data.source_points);
  }
  if (all.length) {
    const box = new THREE.Box3().setFromPoints(all.map(p=>new THREE.Vector3(...p)));
    state.center = box.getCenter(new THREE.Vector3()); state.size = Math.max(...box.getSize(new THREE.Vector3()).toArray(), 1);
    const gridSize = state.size * 3.5;
    state.grid = new THREE.GridHelper(gridSize, 35, 0xcaccc2, 0xd9dcd3); state.grid.rotation.x = Math.PI / 2; state.grid.position.set(state.center.x,state.center.y,box.min.z - state.size*.015); state.grid.material.transparent = true; state.grid.material.opacity=.48; state.scene.add(state.grid);
    const p = data.spec?.parameters;
    if (p) {
      state.dimensions = new THREE.Group(); const offset = state.size*.12;
      state.dimensions.add(makeDimension(new THREE.Vector3(0,p.depth+offset,0),new THREE.Vector3(p.width,p.depth+offset,0),`${number(p.width)} ${data.units==='relative'?'rel':'mm'}`));
      state.dimensions.add(makeDimension(new THREE.Vector3(p.width+offset,0,0),new THREE.Vector3(p.width+offset,p.depth,0),`${number(p.depth)}`));
      state.scene.add(state.dimensions);
    }
    if (!keepCamera) fitCamera();
  }
  applyDisplay();
}

function renderFeatures(spec) {
  const family = spec.family;
  const unit = result?.units === 'relative' ? 'rel' : 'mm';
  const items = [{name:'Reference frame', type:'datum',note:'Canonical object axes',field:null}, {name:'Base sketch',type:'sketch',note:`${number(spec.parameters.width)} × ${number(spec.parameters.depth)} ${unit}`,field:'width'}];
  if (family === 'bracket') items.push({name:'Base extrusion',type:'solid',note:`${number(spec.parameters.thickness)} ${unit}`,field:'thickness'},{name:'Rear wall',type:'solid',note:`${number(spec.parameters.height)} ${unit} total height`,field:'height'});
  else if (family === 'enclosure') items.push({name:'Outer extrusion',type:'solid',note:`${number(spec.parameters.height)} ${unit}`,field:'height'},{name:'Interior pocket',type:'cut',note:`${number(spec.parameters.thickness)} ${unit} wall`,field:'thickness'});
  else items.push({name:'Block extrusion',type:'solid',note:`${number(spec.parameters.height)} ${unit}`,field:'height'});
  (spec.holes || []).forEach((hole,i) => items.push({name:`Through-hole ${i+1}`,type:'cut',note:`Ø ${number(hole.radius*2)} ${unit} · along Z`,field:`hole-${i}-radius`}));
  $('#feature-tree').innerHTML = `<div class="tree-root">${icon('cube',16)}<strong>${escape(label(family))}</strong><span class="tree-count">${items.length}</span></div>${items.map((f,i)=>`<button type="button" class="tree-item" data-feature="${i}" aria-pressed="false"><span class="tree-line"></span><i class="feature-icon ${f.type}">${icon(f.type==='datum'?'fit':f.type==='sketch'?'scan':'layers',14)}</i><span>${escape(f.name)}<small>${escape(f.note)}</small></span></button>`).join('')}`;
  document.querySelectorAll('.tree-item').forEach(btn=>btn.addEventListener('click',()=>{
    document.querySelectorAll('.tree-item').forEach(b=>{b.classList.remove('selected');b.setAttribute('aria-pressed','false');});
    btn.classList.add('selected');btn.setAttribute('aria-pressed','true');
    const field=items[Number(btn.dataset.feature)].field;
    if(!field){fitCamera();$('#canvas-wrap').focus({preventScroll:true});return;}
    const input=$(`[name="${field}"]`);input?.scrollIntoView({block:'nearest',behavior:'instant'});input?.focus({preventScroll:true});
  }));
}
function dimensionField(key,value,description,displayName,accessibleName) {
  const display=Number(value).toFixed(2);
  return `<label class="dimension-row"><span>${escape(displayName||label(key))}<small>${escape(description)}</small></span><div class="dimension-input"><input type="number" name="${escape(key)}" value="${display}" data-initial-value="${Number(value)}" data-initial-display="${display}" min="0.01" max="100000" step="any" required aria-label="${escape(accessibleName||displayName||label(key))}" title="Display rounded to 2 decimals. Unchanged parameters retain full precision."/><span>${result?.units==='relative'?'rel':'mm'}</span></div></label>`;
}
function renderDimensions(spec) {
  const descriptions={width:'X extent',depth:'Y extent',height:'Z extent',thickness:spec.family==='enclosure'?'Wall & bottom':spec.family==='bracket'?'Base & rear wall':'Construction parameter'};
  $('#dimension-fields').innerHTML = Object.entries(spec.parameters).filter(([key])=>key!=='thickness'||spec.family!=='block').map(([key,value])=>dimensionField(key,value,descriptions[key]||'Model parameter')).join('') + (spec.holes || []).map((hole,i)=>`<div class="hole-heading">Through-hole ${i+1}</div>${['x','y','radius'].map(key=>dimensionField(`hole-${i}-${key}`,hole[key],key==='radius'?'Hole radius':`Center ${key.toUpperCase()}`,label(key),`Through-hole ${i+1} ${key}`)).join('')}`).join('');
  $('#dimension-form').querySelectorAll('input').forEach(input=>input.addEventListener('input',()=>{
    input.dataset.dirty='true';clearTimeout(editTimer);$('#edit-status').textContent='Dimension changed. Rebuilding shortly…';
    editTimer=setTimeout(()=>{if($('#dimension-form').checkValidity()) applyEdit();else $('#edit-status').textContent='Enter positive, finite dimensions before rebuilding.';},650);
  }));
}
function renderEvidence(data) {
  const metrics = data.metrics || {};
  const unit = data.units==='relative'?'rel':'mm';
  $('#metric-rmse').innerHTML = `${number(metrics.observed_rmse_mm ?? metrics.rmse_mm,3)}<small>${unit}</small>`;
  $('#metric-chamfer').innerHTML = `${number(metrics.chamfer_mm,3)}<small>${unit}</small>`;
  const valid = metrics.valid ?? metrics.cad_valid ?? data.validation?.valid;
  $('#metric-valid').innerHTML = valid===true?`${icon('check',19)} Valid`:valid===false?'Invalid':'—';
  $('#metric-valid').className = valid===true?'valid-value':valid===false?'invalid-value':'';
  $('#metric-valid-note').textContent=valid===true?'One checked analytic solid':valid===false?'Kernel validation failed':'Kernel check unavailable';
  $('#metric-runtime').innerHTML=`${number(data.runtime_seconds,2)}<small>s</small>`;
  $('#points-count').textContent=`${number(data.source_points?.length || 0,0)} SOURCE POINTS`;
  $('#model-volume').textContent=metrics.volume_mm3!=null?`VOLUME / ${number(metrics.volume_mm3,1)} ${unit==='mm'?'mm³':'rel³'}`:'CAD KERNEL / OPENCASCADE';
}
function renderUncertainty(data) {
  const entries = data.uncertainty || [];
  $('#uncertainty').innerHTML=entries.length?entries.map(item=>`<div class="uncertainty-item"><span class="evidence-status ${escape(item.status || 'unknown')}">${item.status==='observed'?icon('check',13):item.status==='inferred'?'∼':'?'}</span><div><div class="evidence-heading"><strong>${escape(label(item.feature))}</strong><span>${escape(label(item.status))}</span></div><p>${escape(item.detail)}</p></div></div>`).join(''):'<div class="uncertainty-item"><span class="evidence-status unknown">?</span><div><strong>Evidence not quantified</strong><p>Inspect the source overlay before relying on this construction.</p></div></div>';
  const candidates = data.candidates || [];
  $('#candidates').innerHTML=candidates.map((item,i)=>`<div class="candidate ${i===0?'best':''}"><span class="candidate-position">0${i+1}</span><span>${escape(label(item.family))}${i===0?'<small>Selected hypothesis</small>':''}</span><code>${number(item.score,3)}</code>${i===0?icon('check',13):''}</div>`).join('')||'<p class="muted">No candidate scores available.</p>';
  const provenance=data.provenance||{};
  const sourceRows=[['Source',provenance.source_name],['Capture',provenance.source_kind],['Scale',data.units==='mm'?'Millimeters · input/reference supplied':'Relative · no absolute measurement'],['Scoring',provenance.ranking],['Proposal mode',provenance.candidate_mode],['Candidates',provenance.candidate_count],['Refinement',provenance.refined?'Enabled':'Disabled'],['Edited',provenance.edited?'User-specified parameters':null]];
  $('#provenance').innerHTML=sourceRows.filter(([,value])=>value!=null).map(([key,value])=>`<div><span>${escape(key)}</span><strong>${escape(key==='Source'?String(value):label(String(value)))}</strong></div>`).join('');
  const hash=provenance.source_sha256||provenance.sha256;
  if(hash) $('#provenance').innerHTML+=`<div><span>SHA-256</span><code title="${escape(hash)}">${escape(hash.slice(0,12))}…</code></div>`;
  const dataset=provenance.dataset;
  if(dataset){const license=dataset.license||dataset.derived_license||'See dataset provenance';$('#provenance').innerHTML+=`<div><span>Dataset license</span><strong>${escape(typeof license==='string'?license:JSON.stringify(license))}</strong></div>`;}
  $('#warnings').innerHTML=(data.warnings||[]).map(w=>`<div class="warning">${icon('info',15)}<p>${escape(typeof w==='string'?w:JSON.stringify(w))}</p></div>`).join('');
}
function showResult(data, {edit=false,title}={}) {
  result=data;
  if(!edit) originalSpec=structuredClone(data.spec);
  $('#empty-state').hidden=true;$('#viewport-title').hidden=false;
  $('#project-title').textContent=title||$('#project-title').textContent;
  $('#project-source').textContent=`${label(data.provenance?.source_kind||'Source geometry')} · ${data.units==='mm'?'Metric scale supplied':'Scale unknown'}`;
  $('#model-family').textContent=label(data.spec.family);
  $('#model-subtitle').textContent=`Editable construction · ${data.units==='relative'?'relative scale':'millimeters'}`;
  $('#dimension-units').textContent=data.units==='relative'?'relative':'mm';
  const support=data.metrics?.observed_support;
  $('#support-status').hidden=false;
  $('#support-status').className=`support-status ${data.metrics?.accepted===true?'supported':'low-support'}`;
  $('#support-status').textContent=data.metrics?.accepted!==true ? `Hypothesis · review required${Number.isFinite(support)?` · ${number(support*100,0)}% source support`:''}` : `Geometric match${Number.isFinite(support)?` · ${number(support*100,0)}% source support`:''}`;
  $('#project-tag').textContent=data.units==='relative'?'REFERENCE MEASUREMENT REQUIRED':'SCAN → EDITABLE SOLID';
  $('#import-settings-note').textContent=lastFile?`Current upload: ${lastFile.name}. Change units or a reference, then apply.`:'Settings apply to uploaded files. Samples use their supplied units.';
  renderGeometry(data,edit);renderFeatures(data.spec);renderDimensions(data.spec);renderEvidence(data);renderUncertainty(data);
  setBusy(false);$('#edit-status').textContent=edit?'Solid rebuilt. Source geometry is unchanged.':'Dimensions rebuild after a change.';
  $('.feature-note').textContent='An editable construction hypothesis. Hidden geometry requires your review.';
}

async function reconstruct(sample) {
  if(busy) return;
  clearTimeout(editTimer); clearError();
  setBusy(true);
  try {
    lastRequest={sample_id:sample.id,units:sample.units||'mm',ranking:$('#ranking').value,candidate_mode:$('#candidate-mode').value,refine:true};
    const data=await request('/api/reconstruct',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(lastRequest)});
    selectedSample=sample;lastFile=null;
    document.querySelectorAll('.sample-button').forEach(b=>b.classList.toggle('selected',b.dataset.sample===sample.id));
    showResult(data,{title:sample.name});
  } catch(error){showError(`Reconstruction failed: ${error.message}`);setBusy(false);}
}
async function importFile(file) {
  if(!file||busy) return;
  clearTimeout(editTimer);clearError();setBusy(true,'Reading and reconstructing your scan');
  try {
    const form=new FormData(); form.append('file',file);form.append('units',$('#units').value);form.append('ranking',$('#ranking').value);form.append('candidate_mode',$('#candidate-mode').value);form.append('refine','true');form.append('align',String($('#align-pca').checked));
    const reference=$('#reference').value;if(reference) form.append('reference_extent_mm',reference);
    const data=await request('/api/import',{method:'POST',body:form});
    lastFile=file;selectedSample=null;lastRequest=null;
    document.querySelectorAll('.sample-button').forEach(b=>b.classList.remove('selected'));
    showResult(data,{title:file.name.replace(/\.[^.]+$/,'')});
  }catch(error){showError(`Import failed: ${error.message}`);setBusy(false);}finally{$('#file-input').value='';}
}
async function applyEdit(reset=false) {
  if(!result||busy) return;
  clearTimeout(editTimer);clearError();
  let spec=reset?structuredClone(originalSpec):structuredClone(result.spec);
  if(!reset) {
    if(!$('#dimension-form').reportValidity())return;
    $('#dimension-form').querySelectorAll('input').forEach(input=>{
      const key=input.name;const value=input.dataset.dirty==='true'?Number(input.value):Number(input.dataset.initialValue);
      if(key.startsWith('hole-')){const [,i,field]=key.split('-');spec.holes[Number(i)][field]=value;}
      else spec.parameters[key]=value;
    });
  }
  const sequence=++editSequence;
  const focusedField=document.activeElement?.closest('#dimension-form input')?.name;
  setBusy(true,'Rebuilding parametric solid');
  try{const data=await request('/api/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:result.id,spec})});if(sequence===editSequence){showResult(data,{edit:true});if(focusedField)$(`[name="${focusedField}"]`)?.focus({preventScroll:true});}}
  catch(error){showError(`The dimensions could not be applied: ${error.message}`);$('#edit-status').textContent='Last valid solid preserved. Correct the dimensions and retry.';setBusy(false);}
}
function updateExportAvailability(message) {
  const relative=result?.units!=='mm';
  document.querySelectorAll('[data-export]').forEach(button=>{button.disabled=exporting||(relative&&button.dataset.export!=='json');button.title=relative&&button.dataset.export!=='json'?'Supply import units or a reference extent to enable metric export.':'';});
  if(message) $('#export-note').textContent=message;
  else $('#export-note').textContent=relative?'Metric exports need an absolute scale. Set import units or a reference extent, then apply import settings. Project JSON is available at relative scale.':'Review inferred features before manufacturing. STEP and STL preserve geometry; use CadQuery or project JSON to retain parameters.';
}
async function exportModel(format) {
  if(!result||exporting)return;
  if(result.units!=='mm'&&format!=='json'){updateExportAvailability();return;}
  exporting=true;updateExportAvailability('Preparing export…');
  try{
    const response=await fetch(`/api/export/${encodeURIComponent(result.id)}?format=${encodeURIComponent(format)}`);
    if(!response.ok){let body;try{body=await response.json();}catch{}throw new Error(body?.detail||'The export could not be generated.');}
    const blob=await response.blob(); const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`objectdna-${result.spec.family}.${format}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    exporting=false;updateExportAvailability(`${format.toUpperCase()} downloaded. Review inferred features before manufacturing.`);
  }catch(error){exporting=false;updateExportAvailability(error.message);}
}
function jumpToSection(id){const section=$(id);section.scrollIntoView({block:'start',behavior:'instant'});section.focus({preventScroll:true});}
function keyboardView(event){
  const camera=state.camera;if(!camera||!result)return;
  const key=event.key.toLowerCase();
  if(['1','2','3','f'].includes(key)){event.preventDefault();fitCamera(({1:'iso',2:'top',3:'front',f:'iso'})[key]);return;}
  if(!['arrowleft','arrowright','arrowup','arrowdown','+','=','-','_'].includes(key))return;
  event.preventDefault();const offset=camera.position.clone().sub(state.controls.target);let radius=offset.length();
  let theta=Math.atan2(offset.y,offset.x),phi=Math.acos(THREE.MathUtils.clamp(offset.z/radius,-1,1));
  if(key==='arrowleft')theta+=.1;if(key==='arrowright')theta-=.1;if(key==='arrowup')phi-=.1;if(key==='arrowdown')phi+=.1;
  if(key==='+'||key==='=')radius*=.9;if(key==='-'||key==='_')radius*=1.1;
  radius=THREE.MathUtils.clamp(radius,state.size*.15,state.size*30);phi=THREE.MathUtils.clamp(phi,.05,Math.PI*.93);
  offset.set(radius*Math.sin(phi)*Math.cos(theta),radius*Math.sin(phi)*Math.sin(theta),radius*Math.cos(phi));camera.position.copy(state.controls.target).add(offset);state.controls.update();
  document.querySelectorAll('[data-camera]').forEach(button=>{button.classList.remove('active');button.setAttribute('aria-pressed','false');});
}

$('#error-close').addEventListener('click',clearError);
$('#file-input').addEventListener('change',event=>importFile(event.target.files[0]));
['dragover','dragenter'].forEach(type=>$('#dropzone').addEventListener(type,event=>{event.preventDefault();$('#dropzone').classList.add('dragover');}));
['dragleave','drop'].forEach(type=>$('#dropzone').addEventListener(type,event=>{event.preventDefault();$('#dropzone').classList.remove('dragover');if(type==='drop')importFile(event.dataTransfer.files[0]);}));
$('#dimension-form').addEventListener('submit',event=>{event.preventDefault();applyEdit();});
$('#reset-edit').addEventListener('click',()=>applyEdit(true));
$('#apply-import-settings').addEventListener('click',()=>importFile(lastFile));
$('#jump-parameters').addEventListener('click',()=>jumpToSection('#parameter-section'));
$('#jump-evidence').addEventListener('click',()=>jumpToSection('#evidence-section'));
$('#fit-view').addEventListener('click',()=>fitCamera());
$('.canvas-wrap').addEventListener('pointerdown',()=>document.querySelectorAll('[data-camera]').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-pressed','false');}));
$('#canvas-wrap').addEventListener('keydown',keyboardView);
$('[data-view="overlay"]').closest('.view-tabs').addEventListener('click',event=>{const button=event.target.closest('[data-view]');if(!button)return;displayMode=button.dataset.view;document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});applyDisplay();});
document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>fitCamera(b.dataset.camera)));
$('#export-open').addEventListener('click',()=>{updateExportAvailability();$('#export-dialog').showModal();});
$('#export-close').addEventListener('click',()=>$('#export-dialog').close());
$('#export-dialog').addEventListener('click',event=>{if(event.target===$('#export-dialog'))$('#export-dialog').close();});
document.querySelectorAll('[data-export]').forEach(b=>b.addEventListener('click',()=>exportModel(b.dataset.export)));
function rerunSource(){if(selectedSample)reconstruct(selectedSample);else if(lastFile)importFile(lastFile);}
$('#ranking').addEventListener('change',rerunSource);
$('#candidate-mode').addEventListener('change',rerunSource);

init3D();
async function initialize() {
  try{
    const data=await request('/api/samples');sampleList=Array.isArray(data)?data:data.samples||[];
    $('#connection').textContent='Local engine';$('.local-state').classList.add('connected');
    $('#sample-count').textContent=String(sampleList.length).padStart(2,'0');
    $('#samples').innerHTML=sampleList.length?sampleList.map((s,i)=>`<button class="sample-button" data-sample="${escape(s.id)}" title="${escape(s.description || s.name)}"><span class="sample-icon">${icon(s.family==='enclosure'?'cube':s.family==='block'?'scan':'layers',18)}</span><span><strong>${escape(s.name)}</strong><small>${escape(s.source_kind==='real'?'Real scan':s.source_kind||'Sample geometry')}</small></span>${icon('chevron',12)}</button>`).join(''):'<p class="muted">No samples installed. Import your own scan to begin.</p>';
    document.querySelectorAll('.sample-button').forEach(b=>b.addEventListener('click',()=>reconstruct(sampleList.find(s=>s.id===b.dataset.sample))));
    const initial=sampleList.find(s=>s.family==='bracket')||sampleList[0];if(initial)reconstruct(initial);
  }catch(error){$('#connection').textContent='Engine unavailable';$('.local-state').classList.add('disconnected');$('#samples').innerHTML='<p class="muted">Start the ObjectDNA server to load samples.</p>';showError(`Cannot reach the local engine. Start ObjectDNA, then reload this page. ${error.message}`);}
}
initialize();
// Read-only instrumentation used by the repository's browser verification.
window.objectDNA = {get result(){return result;},get displayMode(){return displayMode;},get renderInfo(){return state.renderer?.info;},get viewInfo(){return state.camera?{projection:state.camera.projectionMatrix.toArray(),worldInverse:state.camera.matrixWorldInverse.toArray()}:null;},fitCamera};
