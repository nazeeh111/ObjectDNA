// Controller behavior; rendered HTTP download controls are recorded separately.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../web/src/main.js'),'utf8');
const fragment=source.slice(source.indexOf('function updateExportAvailability('),source.indexOf('\nfunction jumpToSection('));
function harness() {
  let dirty=false,response,calls=0,downloads=[];
  const elements=new Map(),el=s=>{if(!elements.has(s))elements.set(s,{textContent:''});return elements.get(s)};
  const buttons=['step','json'].map(format=>({dataset:{export:format}}));
  const ctx=vm.createContext({result:{id:'original',units:'mm',spec:{family:'bracket'}},busy:false,editTimer:0,
    document:{querySelector(){return dirty?{}:null},querySelectorAll(){return buttons},createElement(){return {click(){downloads.push(this.download)}}}},$:el,
    clearTimeout(){},setTimeout(fn){fn()},URL:{createObjectURL(){return 'blob:test'},revokeObjectURL(){}},
    showError(s){el('error').textContent=s},setBusy(v){ctx.busy=v;ctx.updateExportAvailability()},async fetch(){calls++;return response;}});
  vm.runInContext(fragment,ctx);
  return {ctx,buttons,el,downloads,get calls(){return calls},set dirty(v){dirty=v},set response(v){response=v}};
}
test('export owns busy through body completion and uses the original artifact family',async()=>{
 const h=harness();let release;h.response={ok:true,blob(){return new Promise(r=>release=r)}};
 const pending=h.ctx.exportModel('step');await Promise.resolve();
 assert.equal(h.ctx.busy,true);assert.equal(h.buttons[0].disabled,true);
 await h.ctx.exportModel('step');assert.equal(h.calls,1);
 release({});await pending;assert.equal(h.ctx.busy,false);assert.deepEqual(h.downloads,['objectdna-bracket.step']);
});
test('response body failure preserves result, releases busy and permits retry',async()=>{
 const h=harness(),original=h.ctx.result;h.response={ok:true,async blob(){throw Error('body interrupted')}};
 await h.ctx.exportModel('step');assert.equal(h.ctx.result,original);assert.equal(h.ctx.busy,false);assert.deepEqual(h.downloads,[]);assert.match(h.el('#export-note').textContent,/interrupted/);
 h.response={ok:true,async blob(){return {}}};await h.ctx.exportModel('step');assert.equal(h.calls,2);assert.deepEqual(h.downloads,['objectdna-bracket.step']);
});
test('changed result refuses publication even if ownership is violated externally',async()=>{
 const h=harness();h.response={ok:true,async blob(){h.ctx.result={id:'new',units:'mm',spec:{family:'enclosure'}};return {}}};
 await h.ctx.exportModel('step');assert.equal(h.ctx.busy,false);assert.deepEqual(h.downloads,[]);assert.match(h.el('#export-note').textContent,/changed while exporting/);
});
test('pending dimensions refuse export without changing the draft or fetching',async()=>{
 const h=harness(),original=h.ctx.result;h.dirty=true;await h.ctx.exportModel('step');assert.equal(h.ctx.result,original);assert.equal(h.calls,0);assert.equal(h.ctx.busy,false);assert.match(h.el('error').textContent,/pending dimension/);
});
test('relative scale permits evidence JSON and continues to refuse metric STEP',async()=>{
 const h=harness();h.ctx.result.units='relative';h.ctx.updateExportAvailability();assert.equal(h.buttons[0].disabled,true);assert.equal(h.buttons[1].disabled,false);
 await h.ctx.exportModel('step');assert.equal(h.calls,0);h.response={ok:true,async blob(){return {}}};await h.ctx.exportModel('json');assert.deepEqual(h.downloads,['objectdna-bracket.json']);
});
