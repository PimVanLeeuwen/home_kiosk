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

const VIEWS = ['nas'];

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

function sparkPaths(points, width, height, pad = 6) {
  if (points.length < 2) return { line: '', area: '' };
  const max = Math.max(...points, 0.001);
  const step = width / (points.length - 1);
  const coords = points.map((v, i) => {
    const x = Math.round(i * step);
    const y = Math.round(height - pad - (v / max) * (height - pad * 2));
    return `${x},${y}`;
  });
  const line = `M${coords.join(' L')}`;
  return { line, area: `${line} L${width},${height} L0,${height} Z` };
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

const RENDERERS = { nas: renderNas };

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
