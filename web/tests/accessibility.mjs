import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const baseURL=process.env.OBJECTDNA_URL||'http://127.0.0.1:8768';
const browserName=process.env.OBJECTDNA_BROWSER||'chrome';
const browser=await chromium.launch({...(browserName==='chromium'?{}:{channel:browserName}),headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage();
const reports=[];
try{
 await page.goto(baseURL,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.objectDNA?.result?.id,null,{timeout:180000});
 for(const state of ['workbench','export-dialog']){
  if(state==='export-dialog')await page.locator('#export-open').click();
  const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  reports.push({state,violations:result.violations,passes:result.passes.length,incomplete:result.incomplete.map(rule=>({id:rule.id,description:rule.description,nodes:rule.nodes.map(node=>({target:node.target,summary:node.failureSummary}))}))});
 }
 const folder=path.join(root,'web/.cache/accessibility');await fs.mkdir(folder,{recursive:true});await fs.writeFile(path.join(folder,'report.json'),JSON.stringify(reports,null,2));
 console.log(JSON.stringify(reports.map(r=>({state:r.state,violations:r.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))})),null,2));
 if(reports.some(r=>r.violations.length))process.exitCode=1;
}finally{await browser.close();}
