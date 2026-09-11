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
    // Never substitute the whole portfolio for a smaller filtered selection.
    const files = new Set(stories.map(s => s.file));
    if (box.schema_version !== 2 || box.member_files.length !== files.size || !box.member_files.every(f => files.has(f))) {
      host.insertAdjacentHTML('afterbegin', '<p class="publisher-updated">Showing the current filtered selection. Clear additional filters to see the full publisher report.</p>');
      return;
    }
    host.innerHTML = publisherPage(box);
    initPublisherTabs(host);
  } catch (_) {
    if (request === publisherRequest && state.view === 'publisher') host.insertAdjacentHTML('afterbegin', '<p role="status">The full publisher report is temporarily unavailable. The index summary is shown below.</p>');
  }
}

function publisherPage(box) {
  const e = escHtml;
  const counts = [
    [fmt(box.total_citations), 'Citations'], [fmt(box.total_events), 'Mentions'],
    [`${box.total_works ? Math.round(100 * box.is_open_access / box.total_works) : 0}%`, 'Open access'],
    [fmt(box.country_count), 'Citing countries'],
  ];
  const rank = (title, entries) => `<section><h3>${e(title)}</h3><ul>${entries.map(it => `<li><span>${e(it.label)}</span><strong>${fmt(it.count)}</strong></li>`).join('')}</ul></section>`;
  const labels = {wikipedia:'Wikipedia',reddit:'Reddit',bluesky:'Bluesky',hypothesis:'Expert annotations',stackexchange:'StackExchange',news:'News',other:'Other recorded mentions'};
  const teaching = {library_holdings:'Library holdings',ocw_mentions:'Syllabi / courseware',youtube_mentions:'Educational video lectures',otl_mentions:'Open textbooks',oer_listings:'Open educational resources'};
  const indicators = {has_open_review:'Open peer review',has_prism_context:'PRISM context',has_prism_peer_review:'PRISM peer reviews',has_openaire_reach:'OpenAIRE reach',has_openaire_open_instance:'OpenAIRE open instances'};
  const entries = (obj, names) => Object.entries(obj).map(([key,count]) => ({label:names[key] || key,count}));
  const f = box.featured;
  const feature = f ? `<aside class="publisher-feature"><strong>A closer look</strong><p><a href="${e(f.story_url)}">${e(f.title)}</a> has ${fmt(f.events)} recorded mention${f.events === 1 ? '' : 's'}.</p>${box.featured_evidence.length ? `<p>Examples from Wikipedia article references: ${box.featured_evidence.map(r => `<a href="${e(r.url)}" target="_blank" rel="noopener">${e(r.article)} (checked revision)</a>`).join(' · ')}.</p>` : '<p>Open the work’s story to explore its recorded evidence.</p>'}</aside>` : '';
  // Reuse the existing cover cards, displaying only one ranking at a time.
  const shelf = renderBookshelfCard(box);
  const works = box.items.map(it => `<tr><td>${e(it.year || '—')}</td><td><a href="${e(it.story_url)}">${e(it.title)}</a></td><td>${fmt(it.citations)}</td><td>${fmt(it.events)}</td></tr>`).join('');
  const report = box.report_url ? `<a class="publisher-report" href="${e(box.report_url)}">Printable report</a>` : '<button type="button" class="btn" onclick="printPublisherPage()">Print report</button>';
  return `<header class="publisher-heading"><h1>${e(box.title)}</h1><p>A selection of ${fmt(box.total_works)} ${box.books === box.total_works ? 'books' : 'works'} · ${report}</p></header>
    <div class="publisher-metrics">${counts.map(([n,label]) => `<div class="publisher-metric"><strong>${n}</strong><span>${label}</span></div>`).join('')}</div>
    <p class="publisher-summary">${e(box.summary)}</p>${feature}${shelf}
    <details class="publisher-detail" open><summary>Mentions &amp; reach</summary><p>${e(box.definitions.mentions)}</p><div class="publisher-ranks">${rank('Mentions by platform',entries(box.platform_counts,labels))}${rank('Citing sectors',box.sectors)}</div><p>${e(box.definitions.reach)}</p><div class="publisher-ranks">${rank('Top citing countries',box.countries)}${rank('Top citing institutions',box.institutions)}</div></details>
    <details class="publisher-detail"><summary>Open science &amp; teaching</summary><div class="publisher-ranks">${rank('Works with recorded indicators',entries(box.indicators,indicators))}${rank('Teaching & library evidence',entries(box.teaching,teaching))}${rank('Open access provenance',box.oa_provenance)}</div><p>${fmt(box.claim_gap_count)} works are marked open access by publisher metadata without DOAB confirmation. This is a metadata verification flag.</p></details>
    <details class="publisher-detail"><summary>Scholarly context</summary><div class="publisher-ranks">${rank('Annual citations',Object.entries(box.citations_by_year).map(([label,count])=>({label,count})))}${rank('Inferred roles (heuristic scores)',box.roles)}${rank('Dominant concepts (weighted scores)',box.concepts)}${rank('Funders',box.funders)}</div><p>${fmt(box.top_10_percent_count)} works in the top 10% cited; ${fmt(box.top_1_percent_count)} in the top 1%. Recorded integrity flags: ${fmt(box.retracted_count)} retractions, ${fmt(box.eoc_count)} expressions of concern, ${fmt(box.pubpeer_count)} works with PubPeer discussions.</p></details>
    <details class="publisher-detail"><summary>All ${fmt(box.total_works)} works</summary><div class="publisher-table-wrap"><table class="publisher-table"><thead><tr><th>Year</th><th>Title</th><th>Citations</th><th>Mentions</th></tr></thead><tbody>${works}</tbody></table></div></details>
    <p class="publisher-updated">Overview refreshed ${e(new Date(box.generated_at).toLocaleString('en-GB', {timeZone:'UTC'}))} UTC. Source evidence may have earlier collection dates.<br>${e(box.definitions.coverage)}</p>`;
}

function initPublisherTabs(host) {
  const shelf = host.querySelector('#pfBookshelfCard');
  if (!shelf) return;
  const intro = shelf.querySelector('.pf-card-title + div');
  if (intro) intro.textContent = 'Explore the works behind the evidence.';
  const panels = [...shelf.querySelectorAll('.bookshelf-block')];
  const names = {'Top cited':'Citations','Top mentioned':'Mentions','Top in education':'Teaching'};
  const tabs = document.createElement('div');
  tabs.className = 'publisher-tabs'; tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Bookshelf ranking');
  panels.forEach((panel,i) => {
    const label = panel.querySelector('.bookshelf-label');
    const button = document.createElement('button'); button.type='button';button.setAttribute('role','tab');
    button.id=`publisher-tab-${i}`;button.textContent=names[label.textContent] || label.textContent;
    button.setAttribute('aria-controls',`publisher-panel-${i}`);button.setAttribute('aria-selected',String(i===0));button.tabIndex=i===0?0:-1;
    panel.id=`publisher-panel-${i}`;panel.classList.add('publisher-panel');panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);panel.hidden=i!==0;label.hidden=true;
    button.addEventListener('click',()=>activate(i));tabs.append(button);
  });
  function activate(index) { [...tabs.children].forEach((b,i)=>{b.setAttribute('aria-selected',String(i===index));b.tabIndex=i===index?0:-1;panels[i].hidden=i!==index;}); }
  tabs.addEventListener('keydown',event=>{
    const current=[...tabs.children].indexOf(document.activeElement);let next=current;
    if(event.key==='ArrowRight')next=(current+1)%panels.length;
    else if(event.key==='ArrowLeft')next=(current+panels.length-1)%panels.length;
    else if(event.key==='Home')next=0;else if(event.key==='End')next=panels.length-1;else return;
    event.preventDefault();activate(next);tabs.children[next].focus();
  });
  panels[0].before(tabs);
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
