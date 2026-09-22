/* Headlines — the phone reading view.
 *
 * Separate from app.js on purpose: that drives a fixed 720x1280 board on a
 * 20-second rotation, this is a scrolling document you actually read. It shares
 * only the design tokens and fonts.
 *
 * Reads /api/news/full, which the same collector job writes alongside the kiosk
 * payload — the kiosk's three-per-group is far too thin to read.
 */

const ENDPOINT = '/api/news/full';
const SAVE_ENDPOINT = '/api/save';

// Feed titles are third-party text.
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const time = (d) =>
  `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

function render(data) {
  const groups = (data.groups || []).filter((g) => g.items.length);

  document.getElementById('jump').innerHTML = groups
    .map((g) => `<a href="#g-${esc(g.id)}">${esc(g.title)}</a>`)
    .join('');

  document.getElementById('groups').innerHTML = groups
    .map((g) => `
      <section id="g-${esc(g.id)}">
        <div class="group-head">
          <div class="group-title">${esc(g.title)}</div>
          <div class="group-count">${g.items.length} ITEMS</div>
        </div>
        ${g.items.map((it) => `
          <div class="row">
            <a class="title" href="${esc(it.url)}" target="_blank" rel="noopener noreferrer">
              ${esc(it.title)}
              <span class="meta">
                <span class="source">${esc(it.source).toUpperCase()}</span>
                <span class="age">${esc(it.meta || it.age_label)}</span>
              </span>
            </a>
            <button class="save" type="button"
                    data-url="${esc(it.url)}" data-title="${esc(it.title)}"
                    aria-label="Save to Readeck">＋</button>
          </div>`).join('')}
      </section>`)
    .join('');

  const pulled = document.getElementById('pulled');
  pulled.textContent = `${data.feed_count || 0} FEEDS · ${time(new Date(data.as_of))}`;
  pulled.classList.toggle('is-stale', Boolean(data.stale));
}

async function save(button) {
  if (button.dataset.busy) return;
  button.dataset.busy = '1';
  button.textContent = '…';

  try {
    const res = await fetch(SAVE_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: button.dataset.url, title: button.dataset.title }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `Save failed (${res.status})`);
    button.className = 'save is-saved';
    button.textContent = '✓';
    button.title = 'Saved to Readeck';
  } catch (err) {
    button.className = 'save is-error';
    button.textContent = '!';
    button.title = err.message || 'Save failed';
    // Allow a retry; a saved item stays marked.
    delete button.dataset.busy;
    setTimeout(() => {
      button.className = 'save';
      button.textContent = '＋';
    }, 4000);
  }
}

async function load() {
  try {
    const res = await fetch(ENDPOINT, { cache: 'no-store' });
    if (!res.ok) throw new Error(`collector returned ${res.status}`);
    render(await res.json());
  } catch (err) {
    document.getElementById('groups').innerHTML =
      `<div class="status is-error">Could not reach the collector.<br>${esc(err.message)}</div>`;
  }
}

document.addEventListener('click', (e) => {
  const button = e.target.closest('.save');
  if (button) save(button);
});

// Refresh when the page is returned to, so a phone left open overnight does
// not show yesterday's headlines.
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') load();
});

load();
