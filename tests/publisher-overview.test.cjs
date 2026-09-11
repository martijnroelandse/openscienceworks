const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '..');
const index = fs.readFileSync(path.join(root,'index.html'),'utf8');
// Compile every inline application script as well as the new module.
for (const match of index.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
function setup(fetch) {
 const host = {innerHTML:'fallback',insertAdjacentHTML(_,s){this.innerHTML+=s},querySelector(){return null}};
 const context = vm.createContext({fetch, console, Set, Map, Date,
  state:{view:'publisher',filters:{venue:new Set(['Liverpool University Press'])}},
  document:{addEventListener(){},getElementById(){return host}},
  slugifyPublisher:()=> 'liverpool-university-press',
  escHtml:s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
  fmt:n=>String(n),renderBookshelfCard:()=>'<div>Bookshelf</div>'});
 vm.runInContext(fs.readFileSync(path.join(root,'publisher-overview.js'),'utf8'),context);
 return {context,host};
}
const box = JSON.parse(fs.readFileSync(path.join(root,'publisher_portfolios/liverpool-university-press.json')));
const rows = box.member_files.map(file=>({file}));
test('full publisher displays shared report numbers, mentions and evidence',async()=>{
 const {context,host}=setup(async()=>({ok:true,json:async()=>box}));
 await context.renderPublisherOverview(rows);
 assert.match(host.innerHTML,/Liverpool University Press/);
 assert.match(host.innerHTML,/>28<\/strong><span>Mentions/);
 assert.match(host.innerHTML,/>38<\/strong><span>Citing countries/);
 assert.match(host.innerHTML,/checked revision/);
 assert.match(host.innerHTML,/Printable report/);
 assert.doesNotMatch(host.innerHTML,/all publishers/);
});
test('filtered subset cannot display whole-publisher totals',async()=>{
 const {context,host}=setup(async()=>({ok:true,json:async()=>box}));
 await context.renderPublisherOverview(rows.slice(0,1));
 assert.match(host.innerHTML,/filtered selection/);
 assert.doesNotMatch(host.innerHTML,/publisher-metrics/);
});
test('response arriving after navigation cannot replace a different view',async()=>{
 let resolve;
 const {context,host}=setup(()=>new Promise(r=>{resolve=r}));
 const pending=context.renderPublisherOverview(rows);
 context.state.view='stories';resolve({ok:true,json:async()=>box});await pending;
 assert.equal(host.innerHTML,'fallback');
});
test('failed export keeps usable index summary with explicit status',async()=>{
 const {context,host}=setup(async()=>({ok:false}));
 await context.renderPublisherOverview(rows);
 assert.match(host.innerHTML,/temporarily unavailable/);
 assert.match(host.innerHTML,/fallback/);
});
