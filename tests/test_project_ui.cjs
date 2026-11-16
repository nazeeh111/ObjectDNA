// Controller tests with fake DOM/transport; not visual or real browser acceptance.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../web/src/main.js'),'utf8');
const fragment=source.slice(source.indexOf('async function openProject('),source.indexOf('\nasync function applyEdit('));
function harness() {
  let shown=null,error=null,response=null,dirty=false,downloads=[];
  const elements=new Map();
  const el=id=>{if(!elements.has(id))elements.set(id,{value:'',disabled:false,textContent:'',classList:{remove(){}}});return elements.get(id)};
  const document={querySelector(s){return s.includes('data-dirty')&&dirty?{}:null},querySelectorAll(){return []},createElement(){return {click(){downloads.push(this.download)}}}};
  const ctx=vm.createContext({document,$:el,result:{id:'old',spec:{family:'block'}},busy:false,exporting:false,editTimer:0,editSequence:0,selectedSample:null,lastFile:null,lastRequest:null,
    FormData:class{append(){}},URL:{createObjectURL(){return 'blob:test'},revokeObjectURL(){}},setTimeout(fn){fn()},clearTimeout(){},
    showError(msg){error=msg},clearError(){error=null},setBusy(v){ctx.busy=v},showResult(d,o){shown={d,o};ctx.result=d;ctx.busy=false},
    async request(){if(response instanceof Error)throw response;return response},
    async fetch(){if(response instanceof Error)throw response;return response},console});
  vm.runInContext(fragment,ctx);
  return {ctx,el,get shown(){return shown},get error(){return error},get downloads(){return downloads},set response(v){response=v},set dirty(v){dirty=v}};
}
const file={size:100,name:'saved.json'};
test('open failure preserves the current result; success applies a reopened result',async()=>{
 const h=harness();h.response=Error('invalid project');await h.ctx.openProject(file);
 assert.equal(h.ctx.result.id,'old');assert.match(h.error,/invalid project/);
 h.response={id:'new',spec:{family:'block'}};await h.ctx.openProject(file);
 assert.equal(h.ctx.result.id,'new');assert.equal(h.shown.o.title,'saved');
 assert.match(h.el('#edit-status').textContent,/recomputed/);
});
test('save rejects pending drafts and changed model, and downloads the matching project',async()=>{
 const h=harness();h.dirty=true;await h.ctx.saveProject();assert.match(h.error,/pending/);assert.equal(h.downloads.length,0);
 h.dirty=false;h.response={ok:true,async blob(){h.ctx.result={id:'changed',spec:{family:'block'}};return {}}};await h.ctx.saveProject();assert.match(h.error,/changed while saving/);assert.equal(h.downloads.length,0);
 h.ctx.result={id:'stable',spec:{family:'block'}};h.response={ok:true,async blob(){return {}}};await h.ctx.saveProject();assert.deepEqual(h.downloads,['objectdna-project.json']);
});
test('project input and save handlers are wired in the source',()=>{
 assert.match(source,/project-input'\)\.addEventListener\('change'/);
 assert.match(source,/project-save'\)\.addEventListener\('click',saveProject/);
});
