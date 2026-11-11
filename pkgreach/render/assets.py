"""The page's CSS and script, inlined into ``index.html`` (no external request).

The script is the whole client: it reads the view state from the URL hash
(``#tab=pypi&q=dol&sort=-30d&all=1&noise=1``, keys always in that order),
shows the view, and filters, sorts and shortens its table. Every change
replaces the history entry (a tab here only toggles content), so a link or a
reload reproduces the view and Back leaves the page. Without the script the
page is the All view: every table, full length, with a jump bar.
"""

CSS = """
:root{--bg:#fbfbfa;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--card:#fff;
--accent:#2f6fde;--accent-bg:#e8effc;--up:#1f7a45;--down:#b8322a;--tap:44px}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#141416;
--fg:#ececee;--muted:#a0a0a7;--line:#2c2c30;--card:#1c1c1f;--accent:#7aa7ff;
--accent-bg:#1f2a40;--up:#5cc98a;--down:#ff7b6b}}
[hidden]{display:none!important}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:0 16px}
header.top{padding:14px 0 4px}h1{font-size:1.35rem;margin:0}
header.top p{margin:2px 0 0}
h2{margin:1.4em 0 .4em;font-size:1.1rem}
h3{margin:0 0 .3em;font-size:.95rem;color:var(--muted);font-weight:600}
a{color:var(--accent);text-decoration:none}
.muted{color:var(--muted)}.small{font-size:.85rem}.up{color:var(--up)}.down{color:var(--down)}
.bar{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
.tabs{display:flex;align-items:stretch}
.g1{display:flex;overflow-x:auto;scrollbar-width:none;flex:1 1 auto;min-width:0}
.g1::-webkit-scrollbar{display:none}
.g2{display:flex}
.tabs a,.more-btn,.jump a{display:inline-flex;align-items:center;gap:6px;min-height:var(--tap);
padding:0 12px;white-space:nowrap;color:var(--fg);border:0;background:none;font:inherit;
border-bottom:3px solid transparent;touch-action:manipulation;cursor:pointer}
.tabs a[aria-current]{border-bottom-color:var(--accent);color:var(--accent);font-weight:600}
.tabs .n{font-size:.8rem;color:var(--muted);font-variant-numeric:tabular-nums}
.sep{width:1px;background:var(--line);margin:10px 4px}
.more-btn{display:none;font-size:1.2rem}
.more-btn.cur{color:var(--accent);border-bottom-color:var(--accent)}
.jump{display:flex;overflow-x:auto;border-top:1px solid var(--line)}
.jump a{font-size:.9rem;border:0}
[data-pressed]{opacity:.65;transform:scale(.97);transition:transform 80ms,opacity 80ms}
@media (prefers-reduced-motion:reduce){[data-pressed]{transform:none}}
@media (hover:hover) and (pointer:fine){a:hover{text-decoration:underline}
.tabs a:hover,.btn:hover,th button:hover{background:var(--accent-bg);text-decoration:none}}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(220px,100%),1fr));gap:10px;margin-top:14px}
.card{display:block;color:var(--fg);background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:10px 12px;touch-action:manipulation}
.big{font-size:1.6rem;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.2}
.block{margin-top:6px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
tr:last-child td{border-bottom:0}
.num{text-align:right;white-space:nowrap}
th{font-size:.78rem;color:var(--muted);font-weight:600;line-height:1.2}
th button{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;min-height:36px;
padding:0 2px;cursor:pointer;touch-action:manipulation}
th[aria-sort=descending] button::after{content:" ▾"}th[aria-sort=ascending] button::after{content:" ▴"}
th button[aria-pressed=true]{color:var(--fg)}
th button:focus-visible,.btn:focus-visible,a:focus-visible,.tip:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
td.name{overflow-wrap:break-word;min-width:7em}
td.name .nm{display:block;padding:4px 0}
.chip{display:block;font-size:.75rem;color:var(--muted)}
tr.quiet td{opacity:.55}
.c-spark{width:128px}.spark{width:120px;height:28px;color:var(--accent);display:block}
.mini td.c-spark{width:72px}.mini .spark{width:64px;height:22px}
.badge{font-size:.72rem;border:1px solid var(--line);border-radius:6px;padding:1px 5px;color:var(--muted);white-space:nowrap}
.tag{font-size:.75rem;color:var(--muted);border:1px dashed var(--line);border-radius:6px;padding:0 4px;display:inline-block;line-height:1.3;white-space:normal}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 8px;position:relative}
.q{flex:1 1 220px;min-height:var(--tap);font-size:16px;padding:0 10px;border:1px solid var(--line);
border-radius:8px;background:var(--card);color:var(--fg)}
.sortsel{display:inline-flex;align-items:center;gap:6px;font-size:.9rem;color:var(--muted)}
select{min-height:var(--tap);font-size:16px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);padding:0 6px;max-width:60vw}
.btn,.tip{min-height:var(--tap);padding:0 12px;font:inherit;font-size:.9rem;border:1px solid var(--line);
border-radius:8px;background:var(--card);color:var(--fg);cursor:pointer;touch-action:manipulation}
.btn[aria-pressed=true]{background:var(--accent-bg);border-color:var(--accent);color:var(--accent)}
.tip{min-width:var(--tap);padding:0;font-weight:700;font-style:italic;font-family:Georgia,serif;border-radius:50%}
.tip[aria-expanded=true]{background:var(--accent-bg);border-color:var(--accent)}
.tipbox{flex-basis:100%;margin:0;background:var(--card);border:1px solid var(--accent);border-radius:8px;padding:10px 12px}
.rowsnote{display:flex;gap:10px;align-items:center;margin:8px 0}
.totop{font-weight:400;margin-left:8px;display:none}
details{margin:1.2em 0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 14px}
summary{cursor:pointer;font-weight:600;min-height:var(--tap);display:flex;align-items:center}
footer{margin:2em 0 3em}
.js [data-view]:not(.on){display:none}
html:not(.js) .jsonly{display:none}
html:not(.js) .totop,[data-active=all] .totop{display:inline}
[data-active=all] .tbl .controls,[data-active=all] .tbl .rowsnote{display:none}
@media (max-width:640px){
.c-x,.c-dep{display:none}
.c-spark{width:72px}.spark{width:64px;height:22px}
th,td{padding:4px 6px}
.cards{grid-template-columns:1fr 1fr}.big{font-size:1.3rem}
.two{grid-template-columns:1fr}
.sep{display:none}
.more-btn{display:inline-flex}
.g2{display:none;position:absolute;right:8px;top:100%;flex-direction:column;background:var(--card);
border:1px solid var(--line);border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,.18);min-width:12em}
.g2.open{display:flex}.g2 a{border-bottom:0;border-left:3px solid transparent}
.g2 a[aria-current]{border-left-color:var(--accent)}
.tabs{position:relative}}
@media (min-width:641px){.chip:not(.keep){display:none}}
@media print{.bar,.controls,.rowsnote,.totop{display:none!important}.js [data-view]{display:block!important}
tr[hidden]{display:table-row!important}}
"""

JS = r"""
(()=>{
const H=document.documentElement,D=H.dataset.default,T=H.dataset.title;
const KEYS=['tab','q','sort','all','noise'];
const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const tabs=$$('.tabs a[data-tab]'),views=new Set(tabs.map(a=>a.dataset.tab));
const menu=document.querySelector('.g2'),mbtn=document.querySelector('.more-btn');
let S={};
const parse=h=>{const p=new URLSearchParams(h.replace(/^#/,'')),s={};
KEYS.forEach(k=>{const v=p.get(k);if(v)s[k]=v});return s};
const fmt=s=>'#'+KEYS.filter(k=>s[k]).map(k=>k+'='+encodeURIComponent(s[k])).join('&');
function go(s,top){if(!views.has(s.tab))s={tab:D};S=s;const h=fmt(s);
if(location.hash!==h)history.replaceState(history.state,'',h);show();if(top)scrollTo(0,0)}
function show(){const v=S.tab;H.dataset.active=v;
$$('[data-view]').forEach(el=>el.classList.toggle('on',el.dataset.view.split(' ').includes(v)));
tabs.forEach(a=>a.dataset.tab===v?a.setAttribute('aria-current','page'):a.removeAttribute('aria-current'));
if(mbtn)mbtn.classList.toggle('cur',!!menu.querySelector('[aria-current]'));
const a=tabs.find(a=>a.dataset.tab===v);document.title=a.dataset.title+' · '+T;
$$('section.tbl').forEach(sec=>{const own=sec.dataset.view.split(' ')[0]===v;
if(own)table(sec,S);else if(v==='all')table(sec,{all:1,noise:1,sort:S.sort})})}
function val(r,i){const c=r.cells[i];if(!c)return null;if(c.dataset.s!==undefined)return c.dataset.s;
const v=c.dataset.v;return v===undefined||v===''?null:+v}
function table(sec,st){const tb=sec.querySelector('tbody'),rows=[...tb.rows];
const q=(st.q||'').toLowerCase().trim(),ths=$$('th',sec),has=s=>ths.some(t=>t.dataset.k===s.replace(/^-/,''));
const sort=st.sort&&has(st.sort)?st.sort:(sec.dataset.sort||'');
const desc=sort[0]==='-',k=desc?sort.slice(1):sort,col=ths.findIndex(t=>t.dataset.k===k);
const dir=desc?-1:1,quiet=r=>+r.classList.contains('quiet');
rows.sort((a,b)=>quiet(a)-quiet(b)||(col<0?0:cmp(val(a,col),val(b,col))*dir)||a.dataset.i-b.dataset.i);
function cmp(x,y){if(x===y)return 0;if(x===null)return dir;if(y===null)return -dir;return x<y?-1:1}
const nb=sec.querySelector('.noise'),hideQ=nb&&!st.noise,lim=+sec.dataset.limit||0;let n=0,shown=0;
rows.forEach(r=>{const ok=(!q||r.dataset.q.includes(q))&&!(hideQ&&quiet(r));if(ok)n++;
r.hidden=!ok||(!st.all&&lim&&n>lim);if(!r.hidden)shown++;tb.appendChild(r)});
ths.forEach(t=>{if(!t.dataset.k)return;const on=t.dataset.k===k;
t.setAttribute('aria-sort',on?(desc?'descending':'ascending'):'none');
t.querySelector('button').setAttribute('aria-pressed',on)});
const sel=sec.querySelector('select.sort');if(sel){$$('option.tmp',sel).forEach(o=>o.remove());sel.value=sort;
if(sel.value!==sort&&col>=0){const o=new Option(ths[col].textContent+(desc?' ▾':' ▴'),sort);o.className='tmp';sel.add(o);sel.value=sort}}
if(nb)nb.setAttribute('aria-pressed',!st.noise);
const inp=sec.querySelector('input.q');if(inp&&document.activeElement!==inp)inp.value=st.q||'';
const more=sec.querySelector('.more');if(more){more.hidden=!lim||n<=lim;
more.textContent=st.all?'Show first '+lim:'Show all '+n.toLocaleString()}
const cnt=sec.querySelector('.count');if(cnt)cnt.textContent=q?n+' match'+(n===1?'':'es'):''}
function set(k,v){const s={...S};if(v)s[k]=v;else delete s[k];go(s)}
function closeAll(except){if(menu&&except!==menu){menu.classList.remove('open');mbtn.setAttribute('aria-expanded','false')}
$$('.tip[aria-expanded=true]').forEach(t=>{if(t!==except){t.setAttribute('aria-expanded','false');
document.getElementById(t.getAttribute('aria-controls')).hidden=true}})}
document.addEventListener('click',ev=>{const t=ev.target.closest('a,button');
if(!t){if(!ev.target.closest('.tipbox,.g2'))closeAll();return}
const href=t.getAttribute('href')||'';
if(href.startsWith('#tab=')){ev.preventDefault();closeAll();go(parse(href),true);return}
if(href.startsWith('#')&&t.tagName==='A'){ev.preventDefault();
const el=href==='#top'?null:document.getElementById(href.slice(1));
el?el.scrollIntoView():scrollTo(0,0);return}
if(t===mbtn){const o=!menu.classList.contains('open');closeAll(menu);menu.classList.toggle('open',o);
mbtn.setAttribute('aria-expanded',o);return}
if(t.classList.contains('tip')){const o=t.getAttribute('aria-expanded')!=='true';closeAll(t);
t.setAttribute('aria-expanded',o);document.getElementById(t.getAttribute('aria-controls')).hidden=!o;return}
closeAll();const th=t.closest('th[data-k]');
if(th){const k=th.dataset.k,sec=th.closest('section'),cur=S.sort||sec.dataset.sort||'';
const fresh=k==='name'?k:'-'+k;set('sort',cur===fresh?(fresh[0]==='-'?k:'-'+k):fresh);return}
if(t.classList.contains('more'))set('all',S.all?'':'1');
else if(t.classList.contains('noise'))set('noise',S.noise?'':'1')});
document.addEventListener('input',ev=>{if(ev.target.matches('input.q'))set('q',ev.target.value)});
document.addEventListener('change',ev=>{if(ev.target.matches('select.sort'))set('sort',ev.target.value)});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape')closeAll()});
const unpress=ev=>{const t=ev.target.closest&&ev.target.closest('[data-pressed]');if(t)delete t.dataset.pressed};
document.addEventListener('pointerdown',ev=>{const t=ev.target.closest('a,button,summary');if(t)t.dataset.pressed=''});
['pointerup','pointercancel','pointerout'].forEach(n=>document.addEventListener(n,unpress));
addEventListener('pageshow',()=>$$('[data-pressed]').forEach(t=>delete t.dataset.pressed));
function route(){const h=location.hash.slice(1),el=h&&!h.includes('=')&&document.getElementById(h);
if(el){go({tab:'all'});el.scrollIntoView()}else go(parse(location.hash))}
addEventListener('hashchange',route);route();
})();
"""
