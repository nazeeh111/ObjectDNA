/** Live, end-to-end browser verification. Requires an ObjectDNA server.
 * npm run test:ui -- --record (captures actual UI frames for the demo)
 * OBJECTDNA_URL=http://127.0.0.1:8768 npm run test:ui
 */
import * as THREE from 'three';
import { chromium, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const baseURL=process.env.OBJECTDNA_URL || 'http://127.0.0.1:8768';
const assetRoot=path.join(root,'docs/assets');
const stamp=new Date().toISOString().replaceAll(':','-').replaceAll('.','-');
const run=path.join(process.env.OBJECTDNA_CAPTURE_DIR || path.join(root,'web/.cache/browser-runs'),`capture-${stamp}`);
await fs.mkdir(run,{recursive:true});
const record=process.argv.includes('--record');
const browserName=process.env.OBJECTDNA_BROWSER||'chrome';
const browser=await chromium.launch({...(browserName==='chromium'?{}:{channel:browserName}),headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1,reducedMotion:'reduce'});
const page=await context.newPage();
page.setDefaultTimeout(20000);page.setDefaultNavigationTimeout(30000);
const errors=[];const consoleErrors=[];
page.on('pageerror',error=>{errors.push(error.message);console.error('Page error:',error.message);});
page.on('response',response=>{if(response.url().includes('/api/'))console.log('API',response.status(),response.url());});
page.on('requestfailed',req=>console.error('Request failed:',req.url(),req.failure()));
page.on('console',msg=>{if(msg.type()==='error')consoleErrors.push(msg.text());});
const checks=[];
let frame=0;let recording=false;let recordingTask;
async function startRecording(){if(!record)return;recording=true;recordingTask=(async()=>{while(recording){const started=Date.now();await page.screenshot({path:path.join(run,`frame-${String(frame++).padStart(5,'0')}.png`)});await new Promise(r=>setTimeout(r,Math.max(5,250-(Date.now()-started))));}})();}
async function pause(ms=900){await page.waitForTimeout(ms);}
async function awaitResult(previousId){await page.waitForFunction(id=>window.objectDNA?.result?.id&&window.objectDNA.result.id!==id,previousId,{timeout:240000});await expect(page.locator('#busy-overlay')).toBeHidden();}
async function selectSample(id){const old=await page.evaluate(()=>window.objectDNA.result?.id);await page.locator(`[data-sample="${id}"]`).click();await awaitResult(old);}
async function capture(name){await page.screenshot({path:path.join(run,name),fullPage:false});}
try{
 console.log('Loading',baseURL);
 await page.goto(baseURL,{waitUntil:'domcontentloaded'});
 console.log('DOM loaded; rendering initial screenshot');
 await page.screenshot({path:path.join(run,'initial-load.png'),timeout:20000});
 console.log('Page loaded',await page.title());
 await awaitResult(null);console.log('Initial reconstruction complete');
 await expect(page.locator('#error-banner')).toBeHidden();
 await expect(page.locator('canvas').first()).toBeVisible();
 await expect(page.locator('#model-family')).toHaveText('Bracket');
 const initial=await page.evaluate(()=>({id:window.objectDNA.result.id,spec:window.objectDNA.result.spec,metrics:window.objectDNA.result.metrics,render:window.objectDNA.renderInfo}));
 expect(initial.metrics.valid).toBe(true);expect(initial.render.render.triangles).toBeGreaterThan(0);
 checks.push('Live bracket reconstruction; kernel-valid solid and nonempty WebGL render.');
 await startRecording();await pause(1600);await capture('workbench.png');
 await page.locator('.left-panel').evaluate(el=>el.scrollTop=el.scrollHeight);await pause(800);await capture('feature-tree.png');await page.locator('.left-panel').evaluate(el=>el.scrollTop=0);await pause(500);
 await page.locator('[data-view="source"]').click();await pause(1000);expect(await page.evaluate(()=>window.objectDNA.displayMode)).toBe('source');
 await page.locator('[data-view="cad"]').click();await pause(1000);expect(await page.evaluate(()=>window.objectDNA.displayMode)).toBe('cad');
 await page.locator('[data-view="overlay"]').click();await pause(900);
 await page.locator('[data-camera="top"]').click();await pause(800);await page.locator('[data-camera="iso"]').click();await pause(700);
 await expect(page.locator('[data-view="overlay"]')).toHaveAttribute('aria-pressed','true');
 const cameraBefore=await page.evaluate(()=>window.objectDNA.viewInfo.worldInverse);await page.locator('#canvas-wrap').focus();await page.keyboard.press('ArrowLeft');await pause(150);expect(await page.evaluate(()=>window.objectDNA.viewInfo.worldInverse)).not.toEqual(cameraBefore);await page.keyboard.press('f');
 checks.push('Overlay, source-only and CAD-only modes, pressed semantics, top/iso and keyboard camera controls.');
 const prior=await page.evaluate(()=>window.objectDNA.result.id);
 const editedWidth=initial.spec.parameters.width+10;
 await page.locator('[name="width"]').fill(String(editedWidth));await awaitResult(prior);await pause(1100);
 const edited=await page.evaluate(()=>({spec:window.objectDNA.result.spec,mesh:window.objectDNA.result.mesh,metrics:window.objectDNA.result.metrics}));
 expect(edited.spec.parameters.width).toBeCloseTo(editedWidth,2);
 for(const key of ['depth','height','thickness'])expect(edited.spec.parameters[key]).toBe(initial.spec.parameters[key]);
 expect(Math.max(...edited.mesh.vertices.map(p=>p[0]))).toBeCloseTo(editedWidth,2);
 expect(edited.metrics.valid).toBe(true);await expect(page.locator('[name="width"]')).toBeFocused();
 await expect(page.locator('#support-status')).toContainText('Hypothesis');
 checks.push('Dimension edit rebuilt requested width, preserved exact untouched parameters, retained valid solid and marked user-edited hypothesis.');
 await capture('dimension-edit.png');
 const idBeforeReset=await page.evaluate(()=>window.objectDNA.result.id);await page.locator('#reset-edit').click();await awaitResult(idBeforeReset);await pause(800);
 expect(await page.evaluate(()=>window.objectDNA.result.spec.parameters.width)).toBeCloseTo(initial.spec.parameters.width,5);
 checks.push('Reset restored the reconstructed parameters.');
 const denseId=await page.evaluate(()=>window.objectDNA.result.id);
 await page.locator('#candidate-mode').selectOption('learned_compact');await awaitResult(denseId);
 expect(await page.evaluate(()=>window.objectDNA.result.provenance.candidate_mode)).toBe('learned_compact');
 checks.push('Compact learned proposal mode reaches the backend and reconstructs a valid result.');
 const compactId=await page.evaluate(()=>window.objectDNA.result.id);await page.locator('#candidate-mode').selectOption('dense');await awaitResult(compactId);
 const cereal=page.locator('[data-sample="cereal_box"]');
 if(await cereal.count()){
  await selectSample('cereal_box');await pause(1600);await capture('real-cereal-scan.png');
  expect(await page.evaluate(()=>window.objectDNA.result.provenance.source_kind)).toMatch(/physical|real/i);
  await expect(page.locator('#project-title')).toContainText('cereal');
  checks.push('Physical cereal-box scan reconstructed end to end; capture provenance visible.');
  await page.locator('#export-open').click();
  const downloadPromise=page.waitForEvent('download');await page.locator('[data-export="step"]').click();const download=await downloadPromise;
  const downloaded=path.join(run,'real-cereal-export.step');await download.saveAs(downloaded);expect((await fs.stat(downloaded)).size).toBeGreaterThan(1000);
  await pause(800);await page.locator('#export-close').click();checks.push('Actual STEP download from the physical-object reconstruction.');
 }
 if(await page.locator('[data-sample="porcelain_tray"]').count()){
  await selectSample('porcelain_tray');await pause(1500);await capture('real-failure-case.png');
  await expect(page.locator('#warnings')).not.toBeEmpty();expect(await page.evaluate(()=>window.objectDNA.result.metrics.accepted)).toBe(false);await expect(page.locator('#support-status')).toContainText('Hypothesis');checks.push('Out-of-grammar physical tray exposes warnings and hypothesis status.');
 }
 await selectSample('bracket');
 const source=await page.evaluate(()=>window.objectDNA.result.source_points);
 const beforeImport=await page.evaluate(()=>window.objectDNA.result.id);
 await page.locator('#units').selectOption('unknown');
 await page.locator('#file-input').setInputFiles({name:'relative-bracket.xyz',mimeType:'text/plain',buffer:Buffer.from(source.map(p=>p.join(' ')).join('\n'))});
 await awaitResult(beforeImport);await pause(1100);expect(await page.evaluate(()=>window.objectDNA.result.units)).toBe('relative');
 await page.locator('#export-open').click();await expect(page.locator('[data-export="step"]')).toBeDisabled();await expect(page.locator('[data-export="json"]')).toBeEnabled();
 await expect(page.locator('#export-note')).toContainText(/calibrat|reference|units/i);const relativeId=await page.evaluate(()=>window.objectDNA.result.id);const blocked=await context.request.get(`${baseURL}/api/export/${relativeId}?format=step`);expect(blocked.status()).toBe(422);await pause(1000);await page.keyboard.press('Escape');await expect(page.locator('#export-open')).toBeFocused();
 checks.push('Unknown-scale import exposes JSON-only exports; metric API export blocked; dialog Escape restores keyboard focus.');
 const relativeResult=await page.evaluate(()=>window.objectDNA.result.id);await page.locator('#reference').fill('80');await page.locator('#apply-import-settings').click();await awaitResult(relativeResult);expect(await page.evaluate(()=>window.objectDNA.result.units)).toBe('mm');await expect(page.locator('#provenance')).toContainText('relative-bracket.xyz');
 await page.locator('#export-open').click();await expect(page.locator('[data-export="step"]')).toBeEnabled();await page.keyboard.press('Escape');checks.push('An uploaded relative scan calibrates in place through a reference measurement and metric exports become available.');
 const validId=await page.evaluate(()=>window.objectDNA.result.id);
 await page.locator('#file-input').setInputFiles({name:'malformed.xyz',mimeType:'text/plain',buffer:Buffer.from('not valid geometry')});
 await expect(page.locator('#error-banner')).toBeVisible();expect(await page.evaluate(()=>window.objectDNA.result.id)).toBe(validId);
 await pause(800);await page.locator('#error-close').click();checks.push('Malformed upload rejected while preserving the previous valid solid.');
 await selectSample('drilled-block');await page.locator('.tree-item').filter({hasText:'Through-hole 1'}).click();await expect(page.locator('[name="hole-0-radius"]')).toBeFocused();checks.push('The bore feature tree focuses the correct named hole parameter.');
 await selectSample('bracket');await pause(1200);
 recording=false;if(recordingTask)await recordingTask;
 await page.setViewportSize({width:390,height:844});await pause(700);await capture('workbench-mobile.png');
 const horizontalOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);expect(horizontalOverflow).toBe(false);
 const viewportFit=await page.evaluate(()=>({view:window.objectDNA.viewInfo,vertices:window.objectDNA.result.mesh.vertices}));const worldInverse=new THREE.Matrix4().fromArray(viewportFit.view.worldInverse);const projection=new THREE.Matrix4().fromArray(viewportFit.view.projection);const projected=viewportFit.vertices.map(v=>new THREE.Vector3(...v).applyMatrix4(worldInverse).applyMatrix4(projection));expect(Math.max(...projected.map(v=>Math.abs(v.x)))).toBeLessThan(1);expect(Math.max(...projected.map(v=>Math.abs(v.y)))).toBeLessThan(1);checks.push('390px mobile viewport renders without horizontal overflow; resize fits the model to the new viewport.');
 expect(errors).toEqual([]);
 const scriptPath=await page.locator('script[type="module"]').getAttribute('src');const bundle=await fs.readFile(path.join(root,'web/dist',scriptPath.replace(/^\//,'')));const crypto=await import('node:crypto');
 const report={date:new Date().toISOString(),baseURL,checks,pageErrors:errors,consoleErrors,frames:frame,screenshots:'docs/assets',raw_capture_id:path.basename(run),video_note:'Actual UI frames sampled during the browser run. Playback pacing is capture-dependent, not a runtime benchmark.',browser_bundle:{path:scriptPath,sha256:crypto.createHash('sha256').update(bundle).digest('hex')},initialMetrics:initial.metrics};
 await fs.writeFile(path.join(run,'browser-report.json'),JSON.stringify(report,null,2));
 for(const name of ['workbench.png','feature-tree.png','dimension-edit.png','real-cereal-scan.png','real-failure-case.png','workbench-mobile.png']){try{await fs.copyFile(path.join(run,name),path.join(assetRoot,name));}catch(error){if(error.code!=='ENOENT')throw error;}}
 if(record&&frame>0){
  const output=path.join(run,'walkthrough.mp4');
  const video=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-framerate','4','-i',path.join(run,'frame-%05d.png'),'-c:v','libx264','-pix_fmt','yuv420p','-crf','23','-movflags','+faststart',output],{encoding:'utf8'});
  if(video.status!==0)throw new Error(`ffmpeg demo encoding failed: ${video.stderr}`);
  await fs.copyFile(output,path.join(assetRoot,'walkthrough.mp4'));
 }
 await fs.copyFile(path.join(run,'browser-report.json'),path.join(assetRoot,'browser-report.json'));
 console.log(JSON.stringify(report,null,2));
}catch(error){
 await page.screenshot({path:path.join(run,'failure.png')}).catch(()=>{});
 await fs.writeFile(path.join(run,'failure.json'),JSON.stringify({message:error.message,checks,pageErrors:errors,consoleErrors},null,2));
 throw error;
}finally{recording=false;if(recordingTask)await recordingTask.catch(()=>{});await browser.close();}
