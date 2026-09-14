/* Publisher pages consume the same full-record aggregation as portfolio reports. */
let publisherRequest = 0;
const publisherCache = new Map();

async function renderPublisherOverview(stories) {
  const request = ++publisherRequest;
  if (state.view !== 'publisher' || state.filters.venue.size !== 1) return;
  const name = [...state.filters.venue][0];
  const host = document.getElementById('aggView');
  document.title = `${name} — openscience.works`;
  try {
    let box = publisherCache.get(name);
    if (!box) {
      const response = await fetch(`publisher_portfolios/${slugifyPublisher(name)}.json`, {cache:'no-store'});
      if (!response.ok) throw new Error('Publisher data unavailable');
      box = await response.json();
      publisherCache.set(name, box);
    }
    if (request !== publisherRequest || state.view !== 'publisher' || !state.filters.venue.has(name)) return;
    // The printable report is now the default publisher view — richer, and a
    // plain page load rather than a client-rendered one, so it isn't subject
    // to this SPA's JSON-fetch/render path or its own caching quirks. Only
    // publishers without a generated report (not yet run through the
    // portfolio-dashboard pipeline) fall through to the in-page render below.
    if (box.report_url) {
      window.location.replace(box.report_url);
      return;
    }
    // Never substitute the whole portfolio for a smaller filtered selection.
    const files = new Set(stories.map(s => s.file));
    if (box.schema_version !== 2 || box.member_files.length !== files.size || !box.member_files.every(f => files.has(f))) {
      host.insertAdjacentHTML('afterbegin', '<p class="publisher-updated">Showing the current filtered selection. Clear additional filters to see the full publisher report.</p>');
      return;
    }
    host.innerHTML = publisherPage(box);
    initPublisherTabs(host);
    drawReachMap(document.getElementById('pf-reach-map'));
    renderPublisherCharts(host);
  } catch (_) {
    if (request === publisherRequest && state.view === 'publisher') host.insertAdjacentHTML('afterbegin', '<p role="status">The full publisher report is temporarily unavailable. The index summary is shown below.</p>');
  }
}

function publisherPage(box) {
  const e = escHtml;
  const counts = [
    [fmt(box.total_citations), 'Citations'],
    ...(box.total_downloads ? [[fmt(box.total_downloads), 'Downloads']] : []),
    [fmt(box.total_events), 'Mentions'],
    [`${box.total_works ? Math.round(100 * box.is_open_access / box.total_works) : 0}%`, 'Open access'],
  ];
  const rank = (title, entries, badge) => `<section><h3>${e(title)}${badge ? ` <span class="badge">${e(badge)}</span>` : ''}</h3><ul>${entries.map(it => `<li><span>${e(it.label)}</span><strong>${fmt(it.count)}</strong></li>`).join('')}</ul></section>`;
  const tagCloud = (title, entries, badge) => `<section><h3>${e(title)}${badge ? ` <span class="badge">${e(badge)}</span>` : ''}</h3><div>${entries.map((it, i) => `<span class="pub-tag${i >= 8 ? ' pub-tag-soft' : ''}${i < 3 ? ' pub-tag-1' : i < 8 ? ' pub-tag-2' : ' pub-tag-3'}">${e(it.label)} (${fmt(it.count)})</span>`).join('') || '<span class="publisher-updated">Not available.</span>'}</div></section>`;
  const jsonAttr = (x) => JSON.stringify(x).replace(/'/g, '&#39;');
  const chartCard = (title, badge, id, labels, data) => `<div class="pub-chart-card"><h4>${e(title)}${badge ? ` <span class="badge">${e(badge)}</span>` : ''}</h4><div class="pub-chart-wrap"><canvas id="${id}" data-chart="doughnut" data-labels='${jsonAttr(labels)}' data-values='${jsonAttr(data)}'></canvas></div></div>`;
  const charts = box.total_citations || box.total_events ? `<div class="pub-timeline-wrap"><canvas id="pf-citation-timeline" data-labels='${jsonAttr(Object.keys(box.citations_by_year))}' data-values='${jsonAttr(Object.values(box.citations_by_year))}'></canvas></div>
    <div class="pub-charts-grid">
      ${chartCard('Citing Sectors', 'ROR', 'pf-chart-sectors', box.sectors.map(s => s.label), box.sectors.map(s => s.count))}
      ${chartCard('Citation Context', 'scite', 'pf-chart-scite', ['Supporting', 'Mentioning', 'Contradicting'], [box.scite.supporting, box.scite.mentioning, box.scite.contradicting])}
      ${chartCard('Work Types', 'OpenAlex', 'pf-chart-worktypes', box.work_types.map(w => w.label), box.work_types.map(w => w.count))}
      ${chartCard('Top Venues', 'OpenAlex', 'pf-chart-venues', box.top_venues.map(v => v.label), box.top_venues.map(v => v.count))}
    </div>` : '';
  const labels = {wikipedia:'Wikipedia',reddit:'Reddit',bluesky:'Bluesky',hypothesis:'Expert annotations',stackexchange:'StackExchange',news:'News',other:'Other recorded mentions'};
  const teaching = {library_holdings:'Library holdings',ocw_mentions:'Syllabi / courseware',youtube_mentions:'Educational video lectures',otl_mentions:'Open textbooks',oer_listings:'Open educational resources'};
  const indicatorLabels = {has_open_review:'Open peer review',has_prism_context:'PRISM context',has_prism_peer_review:'PRISM peer reviews',has_openaire_reach:'OpenAIRE reach',has_openaire_open_instance:'OpenAIRE open instances'};
  const entries = (obj, names) => Object.entries(obj).map(([key,count]) => ({label:names[key] || key,count}));
  const osTile = (pct, label) => pct === 0
    ? `<div class="os-tile is-muted"><div class="os-num">&mdash;</div><div class="os-label">${e(label)}</div><div class="os-caption">Not yet recorded — absence of data, not absence of review.</div></div>`
    : `<div class="os-tile"><div class="os-num">${pct}%</div><div class="os-label">${e(label)}</div></div>`;
  const osTiles = box.total_works ? Object.entries(box.indicators).map(([key, count]) =>
    osTile(Math.round(100 * count / box.total_works), indicatorLabels[key] || key)).join('') : '';
  const domainStyle = {academic:['role-pill-academic','#3b82f6','#dbeafe','#1d4ed8'], readership:['role-pill-readership','#8b5cf6','#ede9fe','#6d28d9'],
    public:['role-pill-public','#f59e0b','#fef3c7','#92400e'], practical:['role-pill-practical','#10b981','#dcfce7','#166534']};
  const rolePills = (box.roles && box.roles.length) ? `<div class="pub-roles"><div class="pub-roles-title">Inferred portfolio roles</div>
    <div class="publisher-updated" style="margin-top:.2rem;">What the evidence above doesn't capture — cumulative heuristic classification of how this portfolio is actually used, across all works.</div>
    <div class="roles-row">${box.roles.map(r => {
      const [cls, dot, bg, col] = domainStyle[r.domain] || domainStyle.academic;
      return `<span class="role-pill ${cls}"><span class="role-dot" style="background:${dot};"></span>${e(r.label)}<span class="role-score" style="background:${bg};color:${col};">${Number(r.count).toFixed(1)}</span></span>`;
    }).join('')}</div></div>` : '';
  const qaFlag = box.claim_gap_count ? `<div class="qa-flag"><span class="qa-badge">Needs verification</span>
    <div class="publisher-updated" style="margin-top:.5rem;">${fmt(box.claim_gap_count)} of these works are marked OA by publisher metadata but have no DOAB confirmation — a metadata gap, not necessarily a closed-access work.</div></div>` : '';
  const f = box.featured;
  const feature = f ? `<aside class="publisher-feature"><strong>A closer look</strong><p><a href="${e(f.story_url)}">${e(f.title)}</a> has ${fmt(f.events)} recorded mention${f.events === 1 ? '' : 's'}.</p>${box.featured_evidence.length ? `<p>Examples from Wikipedia article references: ${box.featured_evidence.map(r => `<a href="${e(r.url)}" target="_blank" rel="noopener">${e(r.article)} (checked revision)</a>`).join(' · ')}.</p>` : '<p>Open the work’s story to explore its recorded evidence.</p>'}</aside>` : '';
  // Reuse the existing cover cards, displaying only one ranking per shelf at a time.
  const shelf = renderBookshelfCard(box);
  const map = box.countries.length ? `<section class="pub-map"><h3>Reach, mapped <span class="badge">OpenAlex</span></h3>
    <div class="publisher-updated" style="margin:-.3rem 0 .7rem;">Citing-work affiliations trace back to <strong>${fmt(box.country_count)}</strong> countries — circle size shows citation count from that country.</div>
    <canvas id="pf-reach-map" data-countries='${JSON.stringify(box.countries).replace(/'/g, '&#39;')}' role="img" aria-label="World map of citing countries, sized by citation count"></canvas>
    <div class="pub-map-note">Full breakdown, including countries not shown on the map, in the list below.</div></section>` : '';
  const works = box.items.map(it => `<tr><td>${e(it.year || '—')}</td><td><a href="${e(it.story_url)}">${e(it.title)}</a></td><td>${fmt(it.citations)}</td><td>${fmt(it.events)}</td></tr>`).join('');
  const report = box.report_url ? `<a class="publisher-report" href="${e(box.report_url)}">Printable report</a>` : '<button type="button" class="btn" onclick="printPublisherPage()">Print report</button>';
  return `<header class="publisher-heading"><h1>${e(box.title)}</h1><p>A selection of ${fmt(box.total_works)} ${box.books === box.total_works ? 'books' : 'works'} · ${report}</p></header>
    <div class="publisher-metrics">${counts.map(([n,label]) => `<div class="publisher-metric"><strong>${n}</strong><span>${label}</span></div>`).join('')}</div>
    <div class="publisher-credo"><span class="mark">&#8221;</span><p><b>No single metric stands in for impact here.</b> Every figure below is shown next to the source it came from, so it can be checked — not just cited.</p></div>
    <p class="publisher-summary">${e(box.summary)}</p>${feature}${shelf}${map}
    <details class="publisher-detail" open><summary>Mentions &amp; reach</summary><p>${e(box.definitions.mentions)}</p><div class="publisher-ranks">${rank('Mentions by platform',entries(box.platform_counts,labels))}${rank('Citing sectors',box.sectors,'ROR')}</div><p>${e(box.definitions.reach)}</p><div class="publisher-ranks">${tagCloud('Top citing countries',box.countries,'OpenAlex')}${tagCloud('Top citing institutions',box.institutions,'ROR / OpenAlex')}</div></details>
    <details class="publisher-detail"><summary>Open science &amp; teaching</summary><div class="os-grid">${osTiles}</div>${rolePills}<div class="publisher-ranks" style="margin-top:1.2rem;">${rank('Teaching & library evidence',entries(box.teaching,teaching))}${rank('Open access provenance',box.oa_provenance)}</div>${qaFlag}</details>
    <details class="publisher-detail"><summary>Scholarly context</summary>${charts}<div class="publisher-ranks" style="margin-top:1.2rem;">${tagCloud('Funders',box.funders,'Europe PMC')}${rank('Dominant concepts (weighted scores)',box.concepts)}</div><p>${fmt(box.top_10_percent_count)} works in the top 10% cited; ${fmt(box.top_1_percent_count)} in the top 1%. Recorded integrity flags: ${fmt(box.retracted_count)} retractions, ${fmt(box.eoc_count)} expressions of concern, ${fmt(box.pubpeer_count)} works with PubPeer discussions.</p></details>
    <details class="publisher-detail"><summary>All ${fmt(box.total_works)} works</summary><div class="publisher-table-wrap"><table class="publisher-table"><thead><tr><th>Year</th><th>Title</th><th>Citations</th><th>Mentions</th></tr></thead><tbody>${works}</tbody></table></div></details>
    <p class="publisher-updated">Overview refreshed ${e(new Date(box.generated_at).toLocaleString('en-GB', {timeZone:'UTC'}))} UTC. Source evidence may have earlier collection dates.<br>${e(box.definitions.coverage)}</p>`;
}

const PF_CONTINENTS = [
  [[-165,68],[-140,60],[-125,48],[-123,37],[-117,32],[-106,20],[-97,16],[-88,14],[-80,8],[-77,18],[-95,29],[-97,26],[-82,31],[-76,35],[-70,43],[-60,48],[-65,60],[-80,68],[-100,72],[-130,71],[-165,68]],
  [[-79,9],[-77,1],[-70,-5],[-70,-18],[-71,-30],[-73,-42],[-68,-55],[-63,-53],[-58,-38],[-48,-24],[-35,-8],[-50,3],[-60,9],[-72,10],[-79,9]],
  [[-17,15],[-16,7],[-8,5],[3,6],[9,4],[9,-3],[13,-6],[12,-18],[18,-34],[26,-34],[33,-25],[40,-15],[43,-2],[51,12],[43,12],[37,15],[32,22],[25,32],[10,37],[-6,35],[-13,28],[-17,15]],
  [[-10,52],[-9,43],[-3,36],[3,36],[9,44],[13,38],[19,40],[23,36],[27,40],[29,45],[35,45],[40,46],[48,47],[60,55],[60,66],[40,70],[25,71],[10,63],[5,58],[-10,52]],
  [[35,45],[40,46],[48,47],[60,55],[60,66],[75,68],[90,72],[110,73],[140,73],[170,68],[180,66],[160,60],[145,50],[140,45],[130,35],[122,31],[120,23],[108,10],[100,6],[95,16],[90,22],[88,26],[80,8],[77,8],[68,24],[60,25],[48,30],[44,37],[36,37],[35,45]],
  [[113,-22],[122,-17],[131,-12],[142,-11],[145,-17],[150,-22],[153,-28],[150,-35],[140,-38],[130,-32],[115,-34],[113,-22]]
];

const PF_COUNTRY_CENTROIDS = {
  'United Kingdom':[-2,54],'United States':[-98,39],'Belgium':[4.5,50.6],'China':[104,35],
  'Italy':[12.5,42],'Spain':[-3.7,40],'France':[2.3,47],'Germany':[10.4,51],'Poland':[19.1,52],
  'Netherlands':[5.3,52.2],'Portugal':[-8,39.5],'Ethiopia':[39,9],'Canada':[-96,56],
  'Switzerland':[8.2,46.8],'Lithuania':[24,55.2],'Ireland':[-8,53.4],'Sweden':[16,62],
  'Norway':[9,61],'Denmark':[10,56],'Finland':[26,64],'Austria':[14,47.5],'Greece':[22,39],
  'Turkey':[35,39],'Russia':[90,61],'Ukraine':[31,49],'Czechia':[15.5,49.8],'Czech Republic':[15.5,49.8],
  'Slovakia':[19.5,48.7],'Hungary':[19.5,47.2],'Romania':[25,46],'Bulgaria':[25.5,42.7],
  'Croatia':[15.5,45.1],'Serbia':[21,44],'Slovenia':[14.8,46.1],'Estonia':[25,58.6],
  'Latvia':[25,56.9],'Iceland':[-19,65],'Luxembourg':[6.1,49.8],'Japan':[138,36.2],
  'South Korea':[127.8,36.5],'Korea, Republic of':[127.8,36.5],'India':[79,22],'Pakistan':[69,30],
  'Bangladesh':[90,24],'Indonesia':[113,-2],'Malaysia':[102,4],'Singapore':[103.8,1.35],
  'Thailand':[101,15],'Vietnam':[106,16],'Philippines':[122,13],'Israel':[35,31],
  'Saudi Arabia':[45,24],'United Arab Emirates':[54,24],'Iran':[53,32],'Iraq':[44,33],
  'Egypt':[30,27],'Nigeria':[8,9.5],'South Africa':[24,-29],'Kenya':[38,0.5],
  'Ghana':[-1,7.9],'Morocco':[-6,32],'Tunisia':[9.5,34],'Algeria':[3,28],
  'Brazil':[-52,-11],'Argentina':[-64,-35],'Chile':[-71,-30],'Mexico':[-102,23],
  'Colombia':[-73,4],'Peru':[-75,-10],'Venezuela':[-66,8],'Australia':[134,-25],
  'New Zealand':[172,-41],'Taiwan':[121,23.8],'Hong Kong':[114.1,22.3],
  'Cyprus':[33,35],'Malta':[14.4,35.9],'Georgia':[43.4,42.3],'Armenia':[45,40.1],
  'Ecuador':[-78,-1.8],'Uruguay':[-56,-33],'Costa Rica':[-84,9.7],'Panama':[-80,8.6],
  'Kazakhstan':[68,48],'Uzbekistan':[64,41]
};

function pfPointInPolygon(lon, lat, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
    const intersect = ((yi > lat) !== (yj > lat)) && (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function drawReachMap(canvas) {
  if (!canvas) return;
  let countries;
  try { countries = JSON.parse(canvas.getAttribute('data-countries') || '[]'); }
  catch (e) { countries = []; }
  if (!countries.length) return;
  const ctx = canvas.getContext('2d');

  function draw() {
    const W = canvas.clientWidth || 900;
    const H = Math.round(W * 400 / 900);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    function project(lon, lat) { return [(lon + 180) / 360 * W, (90 - lat) / 180 * H]; }

    const step = W / 108;
    ctx.fillStyle = '#9fb0c7';
    for (let y = step / 2; y < H; y += step) {
      const lat = 90 - (y / H) * 180;
      for (let x = step / 2; x < W; x += step) {
        const lon = (x / W) * 360 - 180;
        let land = false;
        for (let c = 0; c < PF_CONTINENTS.length; c++) { if (pfPointInPolygon(lon, lat, PF_CONTINENTS[c])) { land = true; break; } }
        if (land) { ctx.beginPath(); ctx.arc(x, y, step * 0.19, 0, Math.PI * 2); ctx.fill(); }
      }
    }

    const plottable = countries.filter(c => PF_COUNTRY_CENTROIDS[c.label]);
    if (!plottable.length) return;
    const maxN = Math.max.apply(null, plottable.map(c => c.count));
    plottable.forEach(c => {
      const [lon, lat] = PF_COUNTRY_CENTROIDS[c.label];
      const [x, y] = project(lon, lat);
      const r = 4 + Math.sqrt(c.count / maxN) * 15;
      ctx.beginPath(); ctx.fillStyle = 'rgba(29,78,216,0.32)'; ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.fillStyle = '#1d4ed8'; ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
      ctx.lineWidth = 1.5; ctx.strokeStyle = '#ffffff'; ctx.stroke();
    });

    ctx.font = '600 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillStyle = '#111827';
    ctx.textBaseline = 'middle';
    const placed = [];
    const overlaps = (box) => placed.some(p => box.x < p.x + p.w && box.x + box.w > p.x && box.y < p.y + p.h && box.y + box.h > p.y);
    plottable.slice().sort((a, b) => b.count - a.count).slice(0, 8).forEach(c => {
      const [lon, lat] = PF_COUNTRY_CENTROIDS[c.label];
      const [x, y] = project(lon, lat);
      const r = 4 + Math.sqrt(c.count / maxN) * 15;
      const label = c.label + ' · ' + c.count;
      const w = ctx.measureText(label).width;
      const tx = Math.min(x + r + 6, W - w - 4);
      const bx = { x: tx - 2, y: y - 7, w: w + 4, h: 14 };
      if (overlaps(bx)) return;
      placed.push(bx);
      ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(231,237,245,0.9)'; ctx.strokeText(label, tx, y);
      ctx.fillText(label, tx, y);
    });
  }

  draw();
  let resizeTimer;
  window.addEventListener('resize', function () { clearTimeout(resizeTimer); resizeTimer = setTimeout(draw, 120); });
}

function initPublisherTabs(host) {
  // Two shelves, each a two-way tab switch: cited/education, mentions/downloads —
  // rather than one flat tablist across every ranking. A shelf with only one side
  // of its pair present (e.g. no downloads for a closed-access publisher) just
  // keeps its plain label, no empty tab shown.
  const shelfCard = host.querySelector('#pfBookshelfCard');
  if (!shelfCard) return;
  const pairs = [['Top cited', 'Top in education'], ['Top mentioned', 'Top downloaded']];
  const blocks = [...shelfCard.querySelectorAll('.bookshelf-block')];
  const byLabel = new Map(blocks.map(b => [b.querySelector('.bookshelf-label').textContent, b]));

  pairs.forEach((pair, pairIdx) => {
    const present = pair.map(label => byLabel.get(label)).filter(Boolean);
    if (present.length < 2) return;
    const [blockA, blockB] = present;
    const labelA = blockA.querySelector('.bookshelf-label');
    const labelB = blockB.querySelector('.bookshelf-label');
    const rowA = blockA.querySelector('.bookshelf-row');
    const rowB = blockB.querySelector('.bookshelf-row');
    const idA = `pf-shelf-${pairIdx}-a`, idB = `pf-shelf-${pairIdx}-b`;
    rowA.id = idA; rowB.id = idB;

    const switcher = document.createElement('div');
    switcher.className = 'shelf-tab-switch';
    switcher.setAttribute('role', 'tablist');
    switcher.setAttribute('aria-label', 'Bookshelf ranking');
    const btnA = document.createElement('button');
    btnA.type = 'button'; btnA.className = 'shelf-tab-btn'; btnA.setAttribute('role', 'tab');
    btnA.setAttribute('aria-selected', 'true'); btnA.setAttribute('aria-controls', idA);
    btnA.textContent = labelA.textContent;
    const btnB = document.createElement('button');
    btnB.type = 'button'; btnB.className = 'shelf-tab-btn'; btnB.setAttribute('role', 'tab');
    btnB.setAttribute('aria-selected', 'false'); btnB.setAttribute('aria-controls', idB);
    btnB.textContent = labelB.textContent;
    switcher.append(btnA, btnB);

    labelA.remove(); labelB.remove();
    blockA.insertBefore(switcher, rowA);
    blockA.appendChild(rowB);
    rowB.hidden = true;
    blockB.remove();

    function activate(which) {
      const aOn = which === 'a';
      btnA.setAttribute('aria-selected', String(aOn));
      btnB.setAttribute('aria-selected', String(!aOn));
      rowA.hidden = !aOn;
      rowB.hidden = aOn;
    }
    btnA.addEventListener('click', () => activate('a'));
    btnB.addEventListener('click', () => activate('b'));
  });
}

const PF_PALETTE = ['#2E4563', '#0d9488', '#6366f1', '#f59e0b', '#ec4899', '#0ea5e9', '#8b5cf6', '#14b8a6'];
const PF_DOUGHNUT_OPTS = {
  responsive: true, maintainAspectRatio: false, cutout: '68%',
  plugins: { legend: { position: 'right', labels: { boxWidth: 9, padding: 8, font: { size: 10 } } } }
};

function renderPublisherCharts(host) {
  if (typeof Chart === 'undefined') return;
  host.querySelectorAll('canvas[data-chart="doughnut"]').forEach(canvas => {
    let labels, data;
    try {
      labels = JSON.parse(canvas.getAttribute('data-labels') || '[]');
      data = JSON.parse(canvas.getAttribute('data-values') || '[]');
    } catch (e) { return; }
    const wrap = canvas.closest('.pub-chart-wrap');
    if (!data.length || data.reduce((a, b) => a + b, 0) === 0) {
      if (wrap) wrap.innerHTML = '<div class="publisher-updated" style="display:flex;align-items:center;height:100%;">No data available.</div>';
      return;
    }
    new Chart(canvas.getContext('2d'), {
      type: 'doughnut',
      data: { labels, datasets: [{ data, backgroundColor: PF_PALETTE, borderWidth: 0 }] },
      options: PF_DOUGHNUT_OPTS,
    });
  });

  const timeline = host.querySelector('#pf-citation-timeline');
  if (timeline) {
    const labels = JSON.parse(timeline.getAttribute('data-labels') || '[]');
    const data = JSON.parse(timeline.getAttribute('data-values') || '[]');
    if (data.length && data.some(v => v > 0)) {
      new Chart(timeline.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Citations', data, backgroundColor: '#2E4563', borderRadius: 4 }] },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, border: { display: false }, grid: { color: '#f3f4f6' } },
            x: { grid: { display: false }, border: { display: false } },
          },
          plugins: { legend: { display: false } },
        },
      });
    } else {
      timeline.closest('.pub-timeline-wrap').innerHTML = '<div class="publisher-updated" style="display:flex;align-items:center;height:100%;">No annual citation data available.</div>';
    }
  }
}

function printPublisherPage() {
  const details=[...document.querySelectorAll('.publisher-detail')];const states=details.map(d=>d.open);
  details.forEach(d=>d.open=true);window.print();details.forEach((d,i)=>d.open=states[i]);
}

document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('publisherFilterToggle').addEventListener('click',event=>{
    const expanded=document.body.classList.toggle('publisher-filters-open');event.currentTarget.setAttribute('aria-expanded',String(expanded));
  });
});
