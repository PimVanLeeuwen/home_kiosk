/* Desk dashboard shell.
 *
 * Vanilla JS, no build step. Views are HTML fragments fetched once and rendered
 * in place; data is fetched on the collector's cadence, independently of the
 * rotation, so a view never shows a loading state — only the last good data.
 */

const VIEW_SECONDS = 20;
const POLL_SECONDS = 30;

// Fixtures during M2; the collector once it is reachable.
const API_BASE = new URLSearchParams(location.search).get('api') || './fixtures';
const USING_FIXTURES = !API_BASE.startsWith('http');

const ALL_VIEWS = ['portfolio', 'spotlight', 'news', 'nas'];

// ?view=<name> pins a single view and stops the rotation — for working on one
// screen without waiting for it to come round.
const PINNED = new URLSearchParams(location.search).get('view');
const VIEWS = PINNED && ALL_VIEWS.includes(PINNED) ? [PINNED] : ALL_VIEWS;

/* --- formatting ---------------------------------------------------------- */

const TB = 1e12;
const GB = 1e9;

// Locale month/day names vary by ICU version ("Sept" vs "Sep"), and the design
// depends on a fixed three-letter width.
const DAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

const fmt = {
  // Sub-terabyte values read as nonsense in TB ("0.08 TB"), so switch unit.
  size: (b) => (b >= TB ? `${(b / TB).toFixed(1)} TB` : `${Math.round(b / GB)} GB`),
  pct: (n) => `${Math.round(n)}%`,
  uptime(seconds) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    return `${d}d ${h}h`;
  },
  clock(date) {
    const stamp = `${DAYS[date.getDay()]} ${String(date.getDate()).padStart(2, '0')} ` +
                  `${MONTHS[date.getMonth()]}`;
    return `${stamp} · ${fmt.time(date)}`;
  },
  time: (date) =>
    `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`,
};

/* --- thresholds ---------------------------------------------------------- */

// The artboard renders a 44° drive in amber, so that is the warn line.
const DISK_WARN = 44;
const DISK_CRIT = 55;
const POOL_WARN = 85;
const POOL_CRIT = 95;

const level = (value, warn, crit) =>
  value >= crit ? 'is-crit' : value >= warn ? 'is-warn' : '';

/* --- sparkline ----------------------------------------------------------- */

function sparkPaths(points, width, height, pad = 6, { zeroBased = true } = {}) {
  if (points.length < 2) return { line: '', area: '', last: { x: 0, y: height } };

  // Throughput reads naturally from zero; portfolio values sit far above zero,
  // where a zero-based axis would flatten the whole series into a straight line.
  const hi = Math.max(...points);
  const lo = zeroBased ? 0 : Math.min(...points);
  const span = hi - lo || 1;

  const step = width / (points.length - 1);
  const at = (v, i) => ({
    x: Math.round(i * step),
    y: Math.round(height - pad - ((v - lo) / span) * (height - pad * 2)),
  });

  const coords = points.map(at);
  const line = `M${coords.map((c) => `${c.x},${c.y}`).join(' L')}`;
  return {
    line,
    area: `${line} L${width},${height} L0,${height} Z`,
    last: coords[coords.length - 1],
  };
}

/* --- NAS view ------------------------------------------------------------ */

function renderNas(root, d) {
  const $ = (name) => root.querySelector(`[data-f="${name}"]`);

  $('host').textContent = `${d.host} · up ${fmt.uptime(d.uptime_seconds)}`;
  $('clock').textContent = fmt.clock(new Date());

  $('pools').innerHTML = d.storage.pools
    .map((p) => {
      const state = level(p.used_pct, POOL_WARN, POOL_CRIT);
      const runway =
        p.projection_months === undefined
          ? ''
          : `~${p.projection_months} months at current rate`;
      return `
        <div class="pool ${state}">
          <div class="pool-head">
            <div class="pool-name">${p.name}</div>
            <div class="pool-pct">${fmt.pct(p.used_pct)}</div>
          </div>
          <div class="bar"><span style="width:${p.used_pct}%"></span></div>
          <div class="pool-foot">
            <div>${fmt.size(p.used_bytes)} of ${fmt.size(p.total_bytes)}</div>
            <div class="runway">${runway || `${fmt.size(p.free_bytes)} free`}</div>
          </div>
        </div>`;
    })
    .join('');

  const tile = (name, text, width, warn = false) => {
    $(name).textContent = text;
    $(`${name}-bar`).style.width = `${Math.min(100, width)}%`;
    root.querySelector(`[data-tile="${name}"]`).classList.toggle('is-warn', warn);
  };
  tile('cpu', fmt.pct(d.cpu_pct), d.cpu_pct);
  tile('ram', fmt.pct(d.ram_pct), d.ram_pct, d.ram_pct >= 90);
  tile('temp', d.cpu_temp_c == null ? '—' : `${Math.round(d.cpu_temp_c)}°`, d.cpu_temp_c ?? 0,
       (d.cpu_temp_c ?? 0) >= 80);

  // Running/total, amber when something is stopped — a bare count never moves.
  const stopped = d.containers.total - d.containers.running;
  tile('containers', `${d.containers.running}/${d.containers.total}`,
       d.containers.total ? (d.containers.running / d.containers.total) * 100 : 0,
       stopped > 0);

  const bad = d.disks.filter((x) => x.smart !== 'ok').length;
  $('smart').textContent = bad
    ? `SMART ${bad} ISSUE${bad > 1 ? 'S' : ''} · ${d.disks.length - bad}/${d.disks.length}`
    : `SMART OK · ${d.disks.length}/${d.disks.length}`;

  const disks = $('disks');
  disks.style.gridTemplateColumns = `repeat(${d.disks.length}, minmax(0, 1fr))`;
  disks.innerHTML = d.disks
    .map((x) => {
      const state =
        x.smart === 'fail' ? 'is-crit'
        : x.smart === 'warn' ? 'is-warn'
        : level(x.temp_c ?? 0, DISK_WARN, DISK_CRIT);
      return `
        <div class="disk ${state}">
          <div class="disk-dot"></div>
          <div class="disk-name">${x.name}</div>
          <div class="disk-temp">${x.temp_c == null ? '—' : `${Math.round(x.temp_c)}°`}</div>
        </div>`;
    })
    .join('');

  // Mbps, not MB/s — the artboard label was inconsistent with the payload.
  $('net').textContent = `↓ ${d.network.rx_mbps.toFixed(1)} · ↑ ${d.network.tx_mbps.toFixed(1)} Mbps`;
  // Measured rather than fixed: the card grows to fill the page, and scaling a
  // fixed viewBox to fit would distort the stroke.
  const svg = root.querySelector('.spark');
  const box = svg.getBoundingClientRect();
  const w = Math.round(box.width) || 592;
  const h = Math.round(box.height) || 110;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  const totals = d.network.history.map((p) => p.rx + p.tx);
  const paths = sparkPaths(totals, w, h);
  $('spark-area').setAttribute('d', paths.area);
  $('spark-line').setAttribute('d', paths.line);

  const backup = $('backup');
  if (d.backup.status === 'ok' && d.backup.at) {
    backup.textContent = `BACKUP OK · ${fmt.time(new Date(d.backup.at))}`;
    backup.className = 'foot-status';
  } else if (d.backup.status === 'fail') {
    backup.textContent = 'BACKUP FAILED';
    backup.className = 'foot-status is-fail';
  } else {
    backup.textContent = 'BACKUP STATUS UNKNOWN';
    backup.className = 'foot-status is-stale';
  }

  if (d.stale) {
    backup.textContent = `STALE · ${backup.textContent}`;
    backup.classList.add('is-stale');
  }
}

/* --- portfolio view ------------------------------------------------------ */

const HOLDINGS_SHOWN = 5;   // §5: list is sorted by value, the view shows the top 5
const ALLOC_COLOURS = ['var(--accent)', 'var(--blue)', 'var(--inactive-2)'];

const money = (n, currency) =>
  new Intl.NumberFormat('en-GB', {
    style: 'currency', currency, minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).format(n);

const signed = (n, digits = 1) => `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(digits)}%`;

function renderPortfolio(root, d) {
  const $ = (name) => root.querySelector(`[data-f="${name}"]`);

  $('clock').textContent = fmt.clock(new Date());
  $('total').textContent = money(d.total_value, d.currency);

  const down = d.change.day_pct < 0;
  $('day-pct').textContent = signed(d.change.day_pct, 2);
  $('day-pill').classList.toggle('is-neg', down);
  $('day-abs').textContent =
    `${down ? '−' : '+'}${money(Math.abs(d.change.day_abs), d.currency)} today`;

  for (const [field, value] of [['month', d.change.month_pct],
                                ['year', d.change.year_pct],
                                ['all', d.change.all_pct]]) {
    $(field).textContent = signed(value);
    $(field).classList.toggle('is-neg', value < 0);
  }

  const svg = root.querySelector('.spark');
  const box = svg.getBoundingClientRect();
  const w = Math.round(box.width) || 592;
  const h = Math.round(box.height) || 170;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  const values = d.history.map((p) => p.v);
  // Portfolio values sit far above zero, so a zero-based axis would flatten the
  // line into a straight edge. Scale to the observed range instead.
  const paths = sparkPaths(values, w, h, 10, { zeroBased: false });
  $('spark-area').setAttribute('d', paths.area);
  $('spark-line').setAttribute('d', paths.line);
  const dot = $('spark-dot');
  dot.setAttribute('cx', paths.last.x);
  dot.setAttribute('cy', paths.last.y);

  $('positions').textContent = `${d.holdings.length} POSITIONS`;
  $('holdings').innerHTML = d.holdings
    .slice(0, HOLDINGS_SHOWN)
    .map((h) => `
      <div class="holding">
        <div class="ticker">${h.symbol}</div>
        <div class="holding-name">${h.name}</div>
        <div class="holding-value">${money(h.value, d.currency)}</div>
        <div class="holding-pct ${h.day_pct < 0 ? 'is-neg' : ''}">${signed(h.day_pct)}</div>
      </div>`)
    .join('');

  $('alloc-bar').innerHTML = d.allocation
    .map((a, i) => `<div style="width:${a.pct}%;background:${ALLOC_COLOURS[i % ALLOC_COLOURS.length]}"></div>`)
    .join('');
  $('alloc-legend').innerHTML = d.allocation
    .map((a, i) => `<div><i style="background:${ALLOC_COLOURS[i % ALLOC_COLOURS.length]}"></i>${a.label} ${a.pct}%</div>`)
    .join('');

  const updated = $('updated');
  updated.textContent = `UPDATED ${fmt.time(new Date(d.as_of))}`;
  updated.className = 'foot-status';
  if (d.stale) {
    updated.textContent = `STALE · ${updated.textContent}`;
    updated.classList.add('is-stale');
  }
}

/* --- spotlight view ------------------------------------------------------ */

const MONTHS_TITLE = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// "2023-03" -> "Mar 2023"
function heldSince(value) {
  const [year, month] = String(value).split('-');
  return month ? `${MONTHS_TITLE[Number(month) - 1]} ${year}` : value;
}

// "2026-10-15" -> "15 Oct"
function earningsDate(value) {
  const [, month, day] = String(value).split('-');
  return day ? `${Number(day)} ${MONTHS_TITLE[Number(month) - 1]}` : value;
}

const price = (n, currency) =>
  new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(n);

function renderSpotlight(root, d) {
  const $ = (name) => root.querySelector(`[data-f="${name}"]`);
  const down = d.day_pct < 0;

  $('clock').textContent = fmt.clock(new Date());
  $('symbol').textContent = d.symbol;
  $('meta').textContent = `${d.name} · ${d.exchange}`;
  $('price').textContent = price(d.price, d.currency);

  $('day-pill').textContent =
    `${signed(d.day_pct)} · ${down ? '−' : '+'}${price(Math.abs(d.day_abs), d.currency)}`;
  $('day-pill').classList.toggle('is-neg', down);

  const svg = root.querySelector('.spark');
  const box = svg.getBoundingClientRect();
  const w = Math.round(box.width) || 592;
  const h = Math.round(box.height) || 236;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  const paths = sparkPaths(d.history.map((p) => p.v), w, h, 10, { zeroBased: false });
  $('spark-area').setAttribute('d', paths.area);
  $('spark-line').setAttribute('d', paths.line);
  $('spark-dot').setAttribute('cx', paths.last.x);
  $('spark-dot').setAttribute('cy', paths.last.y);

  $('range52').textContent =
    `${price(d.range_52w.low, d.currency)} — ${price(d.range_52w.high, d.currency)}`;

  const p = d.position;
  $('shares').textContent = p.shares;
  $('avg-cost').textContent = price(p.avg_cost, d.currency);
  $('market-value').textContent = money(p.value, d.currency);
  const lost = p.unrealised_abs < 0;
  $('unrealised').textContent =
    `${lost ? '−' : '+'}${money(Math.abs(p.unrealised_abs), d.currency)}`;
  $('unrealised').style.color = lost ? 'var(--red)' : 'var(--accent)';

  $('weight').textContent = `${p.weight_pct.toFixed(1)}%`;
  $('weight-bar').style.width = `${p.weight_pct}%`;

  // next_earnings is absent, not null, when the source has no date — the cell is
  // dropped and the grid reflows to the remaining facts.
  const facts = [
    ['Day range', `${Math.round(d.day_range.low)} — ${Math.round(d.day_range.high)}`],
    ['Held since', heldSince(p.held_since)],
  ];
  if (d.next_earnings !== undefined) {
    facts.push(['Next earnings', earningsDate(d.next_earnings)]);
  }
  const grid = $('facts');
  grid.style.gridTemplateColumns = `repeat(${facts.length}, minmax(0, 1fr))`;
  grid.innerHTML = facts
    .map(([label, value]) => `
      <div>
        <div class="fact-label">${label}</div>
        <div class="fact-value">${value}</div>
      </div>`)
    .join('');

  const updated = $('updated');
  updated.textContent = `UPDATED ${fmt.time(new Date(d.as_of))}`;
  updated.className = 'foot-status';
  if (d.stale) {
    updated.textContent = `STALE · ${updated.textContent}`;
    updated.classList.add('is-stale');
  }
}

/* --- news view ----------------------------------------------------------- */

// Titles and source names come from third-party feeds, so they are inserted as
// text rather than markup.
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function renderNews(root, d) {
  const $ = (name) => root.querySelector(`[data-f="${name}"]`);
  $('clock').textContent = fmt.clock(new Date());

  // §8: a group with no items is omitted entirely rather than rendered empty.
  const groups = d.groups.filter((g) => g.items.length > 0);

  $('groups').innerHTML = groups
    .map((g) => `
      <div class="card">
        <div class="card-head">
          <div class="card-title">${esc(g.title)}</div>
          ${g.new_count > 0 ? `<div class="new-pill">${g.new_count} NEW</div>` : ''}
        </div>
        <div class="items">
          ${g.items.map((it) => `
            <div class="item" data-url="${esc(it.url)}">
              <div class="item-title">${esc(it.title)}</div>
              <div class="item-meta">
                <span class="source">${esc(it.source).toUpperCase()}</span>
                <span class="item-age">${esc(it.meta || it.age_label)}</span>
              </div>
            </div>`).join('')}
        </div>
      </div>`)
    .join('');

  const pulled = $('pulled');
  const feeds = d.feed_count ? `${d.feed_count} FEEDS · ` : '';
  pulled.textContent = `${feeds}PULLED ${fmt.time(new Date(d.as_of))}`;
  pulled.className = 'foot-status';
  if (d.stale) {
    pulled.textContent = `STALE · ${pulled.textContent}`;
    pulled.classList.add('is-stale');
  }
}

const RENDERERS = {
  portfolio: renderPortfolio,
  spotlight: renderSpotlight,
  news: renderNews,
  nas: renderNas,
};

/* --- shell --------------------------------------------------------------- */

async function boot() {
  const stage = document.getElementById('stage');

  for (const name of VIEWS) {
    const markup = await (await fetch(`./views/${name}.html`)).text();
    const holder = document.createElement('div');
    holder.className = 'slide';
    holder.dataset.name = name;
    holder.innerHTML = markup;
    stage.appendChild(holder);
  }

  async function refresh() {
    for (const name of VIEWS) {
      try {
        const url = USING_FIXTURES ? `${API_BASE}/${name}.json` : `${API_BASE}/api/${name}`;
        const res = await fetch(url, { cache: 'no-store' });
        if (!res.ok) throw new Error(res.status);
        const slide = stage.querySelector(`.slide[data-name="${name}"]`);
        RENDERERS[name](slide, await res.json());
      } catch (err) {
        console.warn(`${name} refresh failed`, err);
      }
    }
  }

  await refresh();
  setInterval(refresh, POLL_SECONDS * 1000);

  // --- rotation ----------------------------------------------------------
  const dots = document.getElementById('dots');
  dots.innerHTML = VIEWS.map(() => '<span></span>').join('');

  let index = 0;
  let startedAt = performance.now();

  function show(next) {
    index = (next + VIEWS.length) % VIEWS.length;
    startedAt = performance.now();
    stage.querySelectorAll('.slide').forEach((el, i) =>
      el.classList.toggle('is-active', i === index));
    [...dots.children].forEach((el, i) => {
      el.classList.toggle('is-active', i === index);
      el.style.removeProperty('--fill');
    });
  }

  function tick(now) {
    const elapsed = (now - startedAt) / 1000;
    const active = dots.children[index];
    if (active) active.style.setProperty('--fill', `${Math.min(100, (elapsed / VIEW_SECONDS) * 100)}%`);
    if (elapsed >= VIEW_SECONDS) show(index + 1);
    requestAnimationFrame(tick);
  }

  show(0);
  requestAnimationFrame(tick);
}

boot();
