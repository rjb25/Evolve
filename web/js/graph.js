import { floor0, isValidTarget, letterHue } from "./board.js";

const NS = "http://www.w3.org/2000/svg";
const SPECIALTY = {
  meat: "var(--meat)",
  water: "var(--water)",
  fiber: "var(--fiber)",
};
const HEALTH_MAX = 20;

function svgEl(name, attrs = {}) {
  const node = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

function svgPoint(svg, ev) {
  const ctm = svg.getScreenCTM();
  if (!ctm) return { x: ev.offsetX, y: ev.offsetY };
  const pt = svg.createSVGPoint();
  pt.x = ev.clientX;
  pt.y = ev.clientY;
  const mapped = pt.matrixTransform(ctm.inverse());
  return { x: mapped.x, y: mapped.y };
}

function nodeRadius(health) {
  return 10 + (Math.min(HEALTH_MAX, floor0(health)) / HEALTH_MAX) * 12;
}

function edgeKey(a, b) {
  return a < b ? `${a}-${b}` : `${b}-${a}`;
}

function livingRows(snapshot) {
  return (snapshot?.survivors || []).filter((row) => row && row.alive);
}

function syncSize(state) {
  const rect = state.svg.getBoundingClientRect();
  const width = Math.max(240, rect.width || 640);
  const height = Math.max(160, rect.height || 260);
  state.width = width;
  state.height = height;
  state.svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
}

function cancelLoop(state) {
  if (state.rafId != null) {
    cancelAnimationFrame(state.rafId);
    state.rafId = null;
  }
}

function tickForces(state) {
  const nodes = [...state.nodes.values()];
  const n = nodes.length;
  if (n === 0) return 0;
  const cx = state.width / 2;
  const cy = state.height / 2;

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const a = nodes[i];
      const b = nodes[j];
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      let dist2 = dx * dx + dy * dy;
      if (dist2 < 0.01) {
        dx = (Math.random() - 0.5) * 0.4;
        dy = (Math.random() - 0.5) * 0.4;
        dist2 = dx * dx + dy * dy;
      }
      const dist = Math.sqrt(dist2);
      const minDist = a.r + b.r + 10;
      const force = 900 / dist2 + (dist < minDist ? (minDist - dist) * 0.08 : 0);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      if (!a.pinned) {
        a.vx -= fx;
        a.vy -= fy;
      }
      if (!b.pinned) {
        b.vx += fx;
        b.vy += fy;
      }
    }
  }

  for (const key of state.edgeEls.keys()) {
    const dash = key.indexOf("-");
    const a = state.nodes.get(Number(key.slice(0, dash)));
    const b = state.nodes.get(Number(key.slice(dash + 1)));
    if (!a || !b) continue;
    let dx = b.x - a.x;
    let dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
    const pull = (dist - 88) * 0.018;
    const fx = (dx / dist) * pull;
    const fy = (dy / dist) * pull;
    if (!a.pinned) {
      a.vx += fx;
      a.vy += fy;
    }
    if (!b.pinned) {
      b.vx -= fx;
      b.vy -= fy;
    }
  }

  let energy = 0;
  for (const node of nodes) {
    if (node.pinned) {
      node.vx = 0;
      node.vy = 0;
      continue;
    }
    node.vx += (cx - node.x) * 0.008;
    node.vy += (cy - node.y) * 0.008;
    node.vx *= 0.82;
    node.vy *= 0.82;
    const speed2 = node.vx * node.vx + node.vy * node.vy;
    if (speed2 > 36) {
      const scale = 6 / Math.sqrt(speed2);
      node.vx *= scale;
      node.vy *= scale;
    }
    node.x += node.vx;
    node.y += node.vy;
    const pad = node.r + 14;
    node.x = Math.max(pad, Math.min(state.width - pad, node.x));
    node.y = Math.max(pad, Math.min(state.height - pad, node.y));
    energy += node.vx * node.vx + node.vy * node.vy;
  }
  return energy;
}

function applyPositions(state) {
  for (const [id, node] of state.nodes) {
    const g = state.nodeEls.get(id);
    if (g) g.setAttribute("transform", `translate(${node.x},${node.y})`);
  }
  for (const [key, line] of state.edgeEls) {
    const dash = key.indexOf("-");
    const a = state.nodes.get(Number(key.slice(0, dash)));
    const b = state.nodes.get(Number(key.slice(dash + 1)));
    if (!a || !b) continue;
    line.setAttribute("x1", String(a.x));
    line.setAttribute("y1", String(a.y));
    line.setAttribute("x2", String(b.x));
    line.setAttribute("y2", String(b.y));
  }
}

function ensureLoop(state) {
  if (state.rafId != null) return;
  const step = () => {
    const energy = tickForces(state);
    applyPositions(state);
    const dragging = Boolean(state.drag);
    if (state.nodes.size === 0) {
      state.rafId = null;
      return;
    }
    if (!dragging && energy < 0.015) {
      state.rafId = null;
      return;
    }
    state.rafId = requestAnimationFrame(step);
  };
  state.rafId = requestAnimationFrame(step);
}

function upsertNodeEl(state, node, snapshot, view) {
  let g = state.nodeEls.get(node.id);
  if (!g) {
    g = svgEl("g", {
      class: "g-node",
      "data-id": String(node.id),
      tabindex: "0",
      role: "button",
    });
    g.append(
      svgEl("circle", { class: "g-body" }),
      svgEl("text", { class: "g-letter", "text-anchor": "middle", dy: "0.35em" }),
      svgEl("text", { class: "g-label", "text-anchor": "middle" })
    );
    state.nodesLayer.appendChild(g);
    state.nodeEls.set(node.id, g);
  }
  const row = node.row;
  const classes = ["g-node"];
  if (view.youId != null && row.id === view.youId) classes.push("you");
  else if (view.watchId != null && row.id === view.watchId) classes.push("watch");
  if (isValidTarget(row, snapshot, view.mode, view.youId)) classes.push("valid");
  if (view.selectedId != null && row.id === view.selectedId) classes.push("selected");
  g.setAttribute("class", classes.join(" "));
  g.dataset.id = String(row.id);
  g.setAttribute("aria-label", `${row.name || ""} #${row.id}`);

  const circle = g.childNodes[0];
  circle.setAttribute("r", String(node.r));
  circle.setAttribute("fill", SPECIALTY[row.produce] || "var(--accent)");

  const letter = String(row.name || "?").slice(0, 1);
  const letterEl = g.childNodes[1];
  letterEl.textContent = letter;
  letterEl.setAttribute("fill", `hsl(${letterHue(letter)}, 78%, 88%)`);

  const label = g.childNodes[2];
  label.textContent = String(row.name || `#${row.id}`);
  label.setAttribute("y", String(node.r + 12));
}

function bindOnce(state) {
  const svg = state.svg;
  if (svg._bound) return;
  svg._bound = true;

  svg.addEventListener("pointerdown", (ev) => {
    const hit = ev.target.closest("[data-id]");
    if (!hit || !svg.contains(hit)) return;
    const id = Number(hit.dataset.id);
    const node = state.nodes.get(id);
    if (!node) return;
    ev.preventDefault();
    const pt = svgPoint(svg, ev);
    state.drag = { id, moved: false, x0: pt.x, y0: pt.y };
    node.pinned = true;
    node.x = pt.x;
    node.y = pt.y;
    try {
      svg.setPointerCapture(ev.pointerId);
    } catch {
      /* capture is best-effort */
    }
    ensureLoop(state);
  });

  svg.addEventListener("pointermove", (ev) => {
    if (!state.drag) return;
    const node = state.nodes.get(state.drag.id);
    if (!node) return;
    const pt = svgPoint(svg, ev);
    if (Math.hypot(pt.x - state.drag.x0, pt.y - state.drag.y0) > 5) {
      state.drag.moved = true;
    }
    node.x = pt.x;
    node.y = pt.y;
    node.vx = 0;
    node.vy = 0;
    applyPositions(state);
  });

  const endDrag = (ev) => {
    if (!state.drag) return;
    const { id, moved } = state.drag;
    const node = state.nodes.get(id);
    if (node) node.pinned = false;
    state.drag = null;
    try {
      svg.releasePointerCapture(ev.pointerId);
    } catch {
      /* already released */
    }
    if (!moved) state.onClick?.(id);
  };
  svg.addEventListener("pointerup", endDrag);
  svg.addEventListener("pointercancel", endDrag);

  svg.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    const hit = ev.target.closest("[data-id]");
    if (!hit || !svg.contains(hit)) return;
    ev.preventDefault();
    const id = Number(hit.dataset.id);
    if (Number.isFinite(id)) state.onClick?.(id);
  });
}

function getState(svg) {
  if (!svg._graph) {
    svg.innerHTML = "";
    const edgesLayer = svgEl("g", { class: "g-edges" });
    const nodesLayer = svgEl("g", { class: "g-nodes" });
    const emptyEl = svgEl("text", {
      class: "g-empty",
      "text-anchor": "middle",
    });
    emptyEl.textContent = "No living survivors.";
    svg.append(edgesLayer, nodesLayer, emptyEl);
    svg._graph = {
      svg,
      nodes: new Map(),
      nodeEls: new Map(),
      edgeEls: new Map(),
      edgesLayer,
      nodesLayer,
      emptyEl,
      rafId: null,
      drag: null,
      onClick: null,
      width: 640,
      height: 260,
      ro: null,
    };
    bindOnce(svg._graph);
  }
  if (!svg._graph.ro && typeof ResizeObserver === "function") {
    svg._graph.ro = new ResizeObserver(() => {
      syncSize(svg._graph);
      ensureLoop(svg._graph);
    });
    svg._graph.ro.observe(svg);
  }
  return svg._graph;
}

export function destroyGraph(svgRoot) {
  const state = svgRoot?._graph;
  if (!state) return;
  cancelLoop(state);
  state.ro?.disconnect();
  state.ro = null;
}

export function renderGraph(svgRoot, snapshot, view = {}, onClick) {
  if (!svgRoot) return;
  const state = getState(svgRoot);
  const opts = view || {};
  state.onClick = onClick || opts.onClick;
  syncSize(state);

  const living = livingRows(snapshot);
  const livingIds = new Set(living.map((row) => row.id));
  const cx = state.width / 2;
  const cy = state.height / 2;

  for (const id of [...state.nodes.keys()]) {
    if (livingIds.has(id)) continue;
    state.nodes.delete(id);
    state.nodeEls.get(id)?.remove();
    state.nodeEls.delete(id);
  }

  living.forEach((row, i) => {
    let node = state.nodes.get(row.id);
    if (!node) {
      const angle = (2 * Math.PI * i) / Math.max(living.length, 1);
      node = {
        id: row.id,
        x: cx + Math.cos(angle) * 90,
        y: cy + Math.sin(angle) * 68,
        vx: 0,
        vy: 0,
        pinned: false,
        r: 14,
        row,
      };
      state.nodes.set(row.id, node);
    }
    node.row = row;
    node.r = nodeRadius(row.health);
    upsertNodeEl(state, node, snapshot, opts);
  });

  const wanted = new Set();
  const pulse = new Set();
  for (const row of living) {
    for (const rid of row.relations || []) {
      if (!livingIds.has(rid)) continue;
      const key = edgeKey(row.id, rid);
      wanted.add(key);
      if (!state.edgeEls.has(key)) {
        const line = svgEl("line", { class: "g-edge", "data-edge": key });
        state.edgesLayer.appendChild(line);
        state.edgeEls.set(key, line);
      }
    }
    const target = row.last_target;
    if (typeof target === "number" && livingIds.has(target)) {
      pulse.add(edgeKey(row.id, target));
    }
  }
  for (const [key, line] of [...state.edgeEls]) {
    if (!wanted.has(key)) {
      line.remove();
      state.edgeEls.delete(key);
      continue;
    }
    line.classList.toggle("pulse", pulse.has(key));
  }

  const empty = living.length === 0;
  state.emptyEl.textContent = snapshot ? "No living survivors." : "Connecting…";
  state.emptyEl.setAttribute("x", String(cx));
  state.emptyEl.setAttribute("y", String(cy));
  state.emptyEl.style.display = empty ? "block" : "none";
  svgRoot.classList.toggle("empty", empty);
  svgRoot.classList.toggle(
    "is-targeting",
    opts.mode === "relate"
  );

  applyPositions(state);
  if (living.length) ensureLoop(state);
  else cancelLoop(state);
}
