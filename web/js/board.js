const GOODS = ["meat", "water", "fiber"];
const GOODS_BAR_MAX = 40;
const HEALTH_MAX = 20;

export function floor0(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return 0;
  return n;
}

export function letterHue(ch) {
  const code = String(ch).toLowerCase().charCodeAt(0);
  if (code < 97 || code > 122) return 0;
  return Math.round(((code - 97) * 360) / 26);
}

export function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function barPct(value, max) {
  if (max <= 0) return 0;
  return Math.max(0, Math.min(100, (floor0(value) / max) * 100));
}

export function renderGlyph(name) {
  const letters = String(name || "").slice(0, 6).padEnd(6, " ");
  return `<div class="glyph" aria-hidden="true">${Array.from(letters)
    .map((ch) => {
      const hue = letterHue(ch);
      const label = /[a-z]/i.test(ch) ? escapeHtml(ch) : "";
      return `<span style="--h:${hue}">${label}</span>`;
    })
    .join("")}</div>`;
}

export function goodBar(kind, value, specialty) {
  const n = floor0(value);
  const pip = specialty === kind ? `<span class="pip" title="specialty"></span>` : "";
  return `<div class="row-bar">
    <span class="lab">${kind}</span>
    <div class="bar ${kind}"><i style="width:${barPct(n, GOODS_BAR_MAX)}%"></i>${pip}</div>
    <span class="num">${n}</span>
  </div>`;
}

export function healthBar(value) {
  const n = Math.min(HEALTH_MAX, floor0(value));
  return `<div class="row-bar">
    <span class="lab">health</span>
    <div class="bar health"><i style="width:${barPct(n, HEALTH_MAX)}%"></i></div>
    <span class="num">${n}</span>
  </div>`;
}

function livingById(snapshot) {
  const map = new Map();
  for (const row of snapshot?.survivors || []) {
    if (row && row.alive) map.set(row.id, row);
  }
  return map;
}

export function isValidTarget(survivor, snapshot, mode, youId) {
  if (!survivor || !survivor.alive) return false;
  const you = (snapshot?.survivors || []).find((row) => row.id === youId);
  if (!you || !you.alive) return false;
  const relations = you.relations || [];
  if (mode === "relate") {
    return survivor.id !== you.id && !relations.includes(survivor.id);
  }
  if (mode === "deal") {
    return relations.includes(survivor.id);
  }
  return false;
}

function tileHtml(row, snapshot, view) {
  const { mode, selectedId, youId, watchId } = view;
  const classes = ["tile"];
  if (youId != null && row.id === youId) classes.push("you");
  else if (watchId != null && row.id === watchId) classes.push("watch");
  if (isValidTarget(row, snapshot, mode, youId)) classes.push("valid");
  if (selectedId != null && row.id === selectedId) classes.push("selected");
  const badges = [];
  if (youId != null && row.id === youId) {
    badges.push(`<span class="badge you">YOU</span>`);
  } else if (watchId != null && row.id === watchId) {
    badges.push(`<span class="badge watch">WATCH</span>`);
  }
  const verb = String(row.action || "none").toUpperCase();
  const relCount = Array.isArray(row.relations) ? row.relations.length : 0;
  return `<article class="${classes.join(" ")}" data-id="${row.id}" role="button" tabindex="0">
    <div class="tile-top">
      ${renderGlyph(row.name)}
      <div class="who">
        <div class="name">${escapeHtml(row.name || "")}</div>
        <div class="id">#${row.id}</div>
        <div class="badges">${badges.join("")}</div>
      </div>
    </div>
    ${healthBar(row.health)}
    ${GOODS.map((g) => goodBar(g, row[g], row.produce)).join("")}
    <div class="tile-foot">
      <span class="chip">${escapeHtml(verb)}</span>
      <span class="rels">rel ${relCount}</span>
    </div>
  </article>`;
}

export function renderBoard(root, snapshot, view = {}, onClick) {
  if (!root) return;
  const opts = view || {};
  const click = onClick || opts.onClick;
  root._onTileClick = click;
  if (!root._bound) {
    root._bound = true;
    root.addEventListener("click", (ev) => {
      const tile = ev.target.closest("[data-id]");
      if (!tile || !root.contains(tile)) return;
      const id = Number(tile.dataset.id);
      if (!Number.isFinite(id)) return;
      root._onTileClick?.(id);
    });
    root.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      const tile = ev.target.closest("[data-id]");
      if (!tile || !root.contains(tile)) return;
      ev.preventDefault();
      const id = Number(tile.dataset.id);
      if (!Number.isFinite(id)) return;
      root._onTileClick?.(id);
    });
  }

  const living = [...livingById(snapshot).values()];
  root.classList.toggle("is-targeting", opts.mode === "deal" || opts.mode === "relate");
  root.classList.toggle("empty", living.length === 0);
  if (!living.length) {
    root.innerHTML = `<div>No living survivors.</div>`;
    return;
  }
  root.innerHTML = living.map((row) => tileHtml(row, snapshot, opts)).join("");
}


