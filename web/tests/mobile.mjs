/** Targeted mobile rendering check; also updates the selected mobile capture. */
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import * as THREE from 'three';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const browserName=process.env.OBJECTDNA_BROWSER||'chrome';
const browser=await chromium.launch({...(browserName==='chromium'?{}:{channel:browserName}),headless:true});
const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});
const page=await context.newPage();
try{
 await page.goto(process.env.OBJECTDNA_URL||'http://127.0.0.1:8768',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.objectDNA?.result?.id,null,{timeout:180000});
 await expect(page.locator('#busy-overlay')).toBeHidden();
 await expect(page.locator('#jump-parameters')).toBeVisible();
 const state=await page.evaluate(()=>({width:window.innerWidth,pageWidth:document.documentElement.scrollWidth,view:window.objectDNA.viewInfo,vertices:window.objectDNA.result.mesh.vertices,background:getComputedStyle(document.querySelector('.viewport-shortcuts')).backgroundColor}));
 expect(state.pageWidth).toBeLessThanOrEqual(state.width+1);expect(state.background).toBe('rgb(248, 249, 242)');
 const inverse=new THREE.Matrix4().fromArray(state.view.worldInverse),projection=new THREE.Matrix4().fromArray(state.view.projection);
 const vertices=state.vertices.map(v=>new THREE.Vector3(...v).applyMatrix4(inverse).applyMatrix4(projection));
 expect(Math.max(...vertices.map(v=>Math.abs(v.x)))).toBeLessThan(1);expect(Math.max(...vertices.map(v=>Math.abs(v.y)))).toBeLessThan(1);
 const axe=await new AxeBuilder({page}).include('.viewport-shortcuts').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(axe.violations).toEqual([]);
 const assets=path.join(root,'docs/assets');await page.screenshot({path:path.join(assets,'workbench-mobile.png')});
 const scriptPath=await page.locator('script[type="module"]').getAttribute('src');const stylesheet=await page.locator('link[rel="stylesheet"]').getAttribute('href');
 const result={date:new Date().toISOString(),viewport:{width:390,height:844},checks:['All mesh vertices project within the viewport.','No horizontal page overflow.','Quick links use an opaque high-contrast background and axe finds zero tagged violations.'],browser_bundle:{path:scriptPath,sha256:crypto.createHash('sha256').update(await fs.readFile(path.join(root,'web/dist',scriptPath.replace(/^\//,'')))).digest('hex')},stylesheet:{path:stylesheet,sha256:crypto.createHash('sha256').update(await fs.readFile(path.join(root,'web/dist',stylesheet.replace(/^\//,'')))).digest('hex')}};
 await page.locator('#jump-parameters').click();await expect(page.locator('#parameter-section')).toBeFocused();
 await fs.writeFile(path.join(assets,'mobile-report.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}
