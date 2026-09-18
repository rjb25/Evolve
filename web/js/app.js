import { renderBoard } from "./board.js";
import { renderGraph } from "./graph.js";
import { renderLog } from "./log.js";
import { connect } from "./protocol.js";
import {
  escapeHtml,
  floor0,
  goodBar,
  healthBar,
  isValidTarget,
  renderGlyph,
} from "./board.js";

const proto = location.protocol === "https:" ? "wss" : "ws";
const wsUrl = `${proto}://${location.host}/Evolution/ws${location.search}`;

const SPEEDS = [0.5, 1, 2, 5, 10];
const POP_CAP = 10;

const els = {
  board: document.getElementById("board"),
  panel: document.getElementById("panel"),
  banner: document.getElementById("banner"),
  error: document.getElementById("error"),
  playpause: document.getElementById("btn-playpause"),
  step: document.getElementById("btn-step"),
  speeds: document.getElementById("speeds"),
  timeoutRemaining: document.getElementById("timeout-remaining"),
  timeoutS: document.getElementById("timeout-s"),
  alive: document.getElementById("alive"),
  humans: document.getElementById("humans"),
  tick: document.getElementById("tick"),
  graph: document.getElementById("graph"),
  log: document.getElementById("log"),
  lobbyView: document.getElementById("lobby-view"),
  playView: document.getElementById("play-view"),
  lobbyRows: document.getElementById("lobby-rows"),
  lobbyTable: document.getElementById("lobby-table"),
  lobbyEmpty: document.getElementById("lobby-empty"),
  lobbyError: document.getElementById("lobby-error"),
  newGame: document.getElementById("btn-new-game"),
  lobbySeed: document.getElementById("lobby-seed"),
};

let snapshot = null;
let targeting = null;
let selectedId = null;
let send = () => {};

function survivorById(id) {
  if (id == null || !snapshot) return null;
  return (snapshot.survivors || []).find((row) => row.id === id) || null;
}

function livingList() {
  return (snapshot?.survivors || []).filter((row) => row && row.alive);
}

function pickSuccessor(survivors) {
  let best = null;
  for (const row of survivors || []) {
    if (!row || !row.alive) continue;
    if ((snapshot?.humans || []).includes(row.id)) continue;
    if (
      best == null ||
      row.health > best.health ||
      (row.health === best.health && row.id < best.id)
    ) {
      best = row;
    }
  }
  return best ? best.id : null;
}

function isAwaitingPossess(snap) {
  return Boolean(
    snap && (snap.clock?.mode === "awaiting_possess" || snap.pending_possess)
  );
}

function isExtinct(snap) {
  if (!snap) return false;
  if (snap.clock?.mode === "extinct") return true;
  return (snap.population || 0) === 0 && livingList().length === 0;
}

function stepEnabled(snap) {
  if (!snap) return false;
  const mode = snap.clock?.mode;
  if (mode === "watching") return true;
  if (mode === "pause") {
    return (
      snap.control_id == null &&
      !snap.pending_possess &&
      (snap.population || 0) > 0
    );
  }
  return false;
}

function actsEnabled(snap) {
  if (snap?.clock?.mode !== "awaiting_player" || snap.control_id == null) {
    return false;
  }
  const waiting = snap.waiting || [];
  if (waiting.length && !waiting.includes(snap.control_id)) return false;
  return true;
}

function isHost(snap) {
  return snap?.host !== false;
}

function formatTimeout(clock) {
  if (!clock) return "—";
  if (clock.timeout_ms === 0) return "∞";
  const ms = clock.timeout_remaining_ms;
  if (ms == null) return "—";
  return `${(floor0(ms) / 1000).toFixed(1)}s`;
}

function dealPreviewText(preview) {
  const excess = preview?.excess;
  const need = preview?.need;
  if (!excess || !need) return "";
  return `offer ${excess} (−9) for ${need} (+10); they accept if their ${need} > their ${excess} − 1`;
}

function livingRelations(actor) {
  if (!actor) return [];
  const living = new Set(livingList().map((row) => row.id));
  return (actor.relations || []).filter((id) => living.has(id));
}

function relateCandidates(actor) {
  if (!actor) return [];
  const related = new Set(actor.relations || []);
  return livingList().filter((row) => row.id !== actor.id && !related.has(row.id));
}

function clearTargetIfInvalid() {
  if (!snapshot || !targeting) {
    selectedId = null;
    return;
  }
  const you = survivorById(snapshot.control_id);
  if (!actsEnabled(snapshot) || !you || !you.alive) {
    targeting = null;
    selectedId = null;
    return;
  }
  if (targeting === "deal" && livingRelations(you).length === 0) {
    targeting = null;
    selectedId = null;
    return;
  }
  if (targeting === "relate" && relateCandidates(you).length === 0) {
    targeting = null;
    selectedId = null;
    return;
  }
  if (selectedId == null) return;
  const target = survivorById(selectedId);
  if (!isValidTarget(target, snapshot, targeting, snapshot.control_id)) {
    selectedId = null;
  }
}

function handleSurvivorClick(id) {
  if (!snapshot || !Number.isFinite(id)) return;
  const target = survivorById(id);
  if (!target || !target.alive) return;
  const you = survivorById(snapshot.control_id);
  const youAlive = Boolean(you && you.alive);

  if (
    targeting === "relate" &&
    youAlive &&
    isValidTarget(target, snapshot, "relate", snapshot.control_id)
  ) {
    selectedId = id;
    render();
    return;
  }
  if (
    targeting === "deal" &&
    youAlive &&
    isValidTarget(target, snapshot, "deal", snapshot.control_id)
  ) {
    selectedId = id;
    render();
    return;
  }
  if (isAwaitingPossess(snapshot)) {
    send({ op: "possess", id });
    return;
  }
  send({ op: "spectate", id });
}

function confirmTargetedAct() {
  if (!actsEnabled(snapshot) || !targeting || selectedId == null) return;
  if (targeting === "deal") {
    send({ op: "act", action: "deal", target_id: selectedId });
  } else if (targeting === "relate") {
    send({ op: "act", action: "relate", target_id: selectedId });
  }
  targeting = null;
  selectedId = null;
}

function setTargeting(mode) {
  if (!actsEnabled(snapshot)) return;
  if (targeting === mode) {
    targeting = null;
    selectedId = null;
  } else {
    targeting = mode;
    selectedId = null;
  }
  render();
}

function renderChrome() {
  const clock = snapshot?.clock;
  const paused = clock?.mode === "pause";
  els.playpause.textContent = paused ? "Play" : "Pause";
  const host = isHost(snapshot);
  els.playpause.disabled = !snapshot || !host;
  els.step.disabled = !host || !stepEnabled(snapshot);
  els.timeoutS.disabled = !snapshot || !host;
  const speed = Number(clock?.speed);
  for (const btn of els.speeds.querySelectorAll("[data-speed]")) {
    const value = Number(btn.dataset.speed);
    btn.classList.toggle("active", Number.isFinite(speed) && Math.abs(speed - value) < 1e-6);
  }
  els.timeoutRemaining.textContent = formatTimeout(clock);
  const living = snapshot ? snapshot.population ?? livingList().length : "—";
  els.alive.textContent = `Alive ${living}/${POP_CAP}`;
  const humanN = snapshot?.humans ? snapshot.humans.length : 0;
  if (els.humans) els.humans.textContent = `Humans ${humanN}`;
  els.tick.textContent = `Tick ${snapshot ? snapshot.tick : "—"}`;
}

function renderPanel() {
  const root = els.panel;
  if (!snapshot) {
    root.innerHTML = `<h2>YOU / SPECTATE</h2><p class="sub">Connecting…</p>`;
    return;
  }
  const subjectId = snapshot.spectate_id ?? snapshot.control_id;
  const subject = survivorById(subjectId);
  const you = survivorById(snapshot.control_id);
  const isYou = Boolean(
    subject && snapshot.control_id != null && subject.id === snapshot.control_id
  );
  const title = isYou ? "YOU" : "SPECTATE";
  const canAct = isYou && actsEnabled(snapshot);
  const rels = livingRelations(subject);
  const dealOk = canAct && livingRelations(you).length > 0;
  const relateOk = canAct && relateCandidates(you).length > 0;
  const preview = dealPreviewText(snapshot.deal_preview);
  const selected = selectedId != null ? survivorById(selectedId) : null;

  let body = `<h2>${title}</h2>`;
  if (!subject || !subject.alive) {
    body += `<p class="sub">No survivor under watch.</p>`;
  } else {
    body += `<div class="tile-top">
      ${renderGlyph(subject.name)}
      <div class="who">
        <div class="name">${escapeHtml(subject.name || "")}</div>
        <div class="id">#${subject.id}</div>
      </div>
    </div>
    ${healthBar(subject.health)}
    ${["meat", "water", "fiber"].map((g) => goodBar(g, subject[g], subject.produce)).join("")}
    <p class="caption">specialty: ${escapeHtml(subject.produce || "—")}</p>
    <h3 class="sub">Relations</h3>
    ${
      rels.length
        ? `<ul class="relations">${rels
            .map((id) => {
              const row = survivorById(id);
              const name = row ? row.name : id;
              return `<li><button type="button" data-id="${id}">${escapeHtml(name)} #${id}</button></li>`;
            })
            .join("")}</ul>`
        : `<p class="sub">None.</p>`
    }`;
  }

  if (canAct) {
    body += `<div class="actions">
      <button type="button" data-act="produce">Produce</button>
      <button type="button" data-mode="deal" ${dealOk ? "" : "disabled"} aria-pressed="${targeting === "deal"}">Deal</button>
      <button type="button" data-mode="relate" ${relateOk ? "" : "disabled"} aria-pressed="${targeting === "relate"}">Relate</button>
      <button type="button" data-act="produce">Skip (produce)</button>
    </div>`;
    if (targeting === "deal") {
      body += `<div class="preview">${escapeHtml(preview || "Select a living relation.")}`;
      if (selected) {
        body += `<div>target: ${escapeHtml(selected.name)} #${selected.id}</div>
          <button type="button" data-confirm="deal">Confirm deal</button>`;
      }
      body += `</div>`;
    } else if (targeting === "relate") {
      body += `<div class="preview">Select a living survivor you are not already related to.`;
      if (selected) {
        body += `<div>target: ${escapeHtml(selected.name)} #${selected.id}</div>
          <button type="button" data-confirm="relate">Confirm relate</button>`;
      }
      body += `</div>`;
    }
  } else if (
    snapshot.control_id != null &&
    subject &&
    subject.id !== snapshot.control_id
  ) {
    body += `<p class="sub">Watching ${escapeHtml(subject.name)}. Click your tile to return.</p>`;
  }

  if (snapshot.control_id != null || snapshot.pending_possess) {
    body += `<div class="panel-foot">
      <button type="button" data-release="1">Release control (watch only)</button>
    </div>`;
  }

  root.innerHTML = body;
}

function renderBanner() {
  const el = els.banner;
  if (!snapshot) {
    el.className = "banner hidden";
    el.innerHTML = "";
    return;
  }
  if (isExtinct(snapshot)) {
    el.className = "banner extinct";
    el.innerHTML = `<span>Extinction. New run.</span>
      <button type="button" data-op="reset">New run</button>`;
    return;
  }
  if (snapshot.clock?.mode === "awaiting_possess" || snapshot.pending_possess) {
    const name = snapshot.died_as_name || "a survivor";
    el.className = "banner";
    el.innerHTML = `<span>You died as ${escapeHtml(name)}. Possess a living survivor, or Auto.</span>
      <button type="button" data-op="auto">Auto</button>`;
    return;
  }
  const waiting = snapshot.waiting || [];
  if (
    snapshot.control_id != null &&
    waiting.length &&
    !waiting.includes(snapshot.control_id)
  ) {
    el.className = "banner";
    el.innerHTML = `<span>Waiting for other players…</span>`;
    return;
  }
  el.className = "banner hidden";
  el.innerHTML = "";
}

function render() {
  clearTargetIfInvalid();
  renderChrome();
  if (!snapshot) {
    els.board.classList.add("empty");
    els.board.classList.remove("is-targeting");
    els.board.innerHTML = `<div>Connecting…</div>`;
  } else {
    renderBoard(
      els.board,
      snapshot,
      {
        mode: targeting,
        selectedId,
        youId: snapshot.control_id ?? null,
        watchId: snapshot.spectate_id ?? null,
        humans: snapshot.humans || [],
      },
      handleSurvivorClick
    );
  }
  renderPanel();
  renderBanner();
  renderGraph(
    els.graph,
    snapshot,
    snapshot
      ? {
          mode: targeting,
          selectedId,
          youId: snapshot.control_id ?? null,
          watchId: snapshot.spectate_id ?? null,
          humans: snapshot.humans || [],
        }
      : {},
    handleSurvivorClick
  );
  renderLog(els.log, snapshot);
}

function showError(frame) {
  const detail = frame?.detail || frame?.error || "error";
  els.error.textContent = detail;
  els.error.classList.remove("hidden");
}

function clearError() {
  els.error.classList.add("hidden");
  els.error.textContent = "";
}

function onSnapshot(next) {
  snapshot = next;
  clearError();
  render();
}

function onError(frame) {
  showError(frame);
}

function onClose(ev) {
  const code = ev && ev.code != null ? ev.code : "";
  showError({ detail: code ? `disconnected (${code})` : "disconnected" });
}

function showLobbyError(text) {
  if (!els.lobbyError) return;
  els.lobbyError.textContent = text;
  els.lobbyError.classList.toggle("hidden", !text);
}

function renderLobbyList(rows) {
  const list = rows || [];
  if (els.lobbyEmpty) els.lobbyEmpty.classList.toggle("hidden", list.length > 0);
  if (els.lobbyTable) els.lobbyTable.classList.toggle("hidden", list.length === 0);
  if (!els.lobbyRows) return;
  els.lobbyRows.innerHTML = list
    .map((row) => {
      const joinable = row.joinable;
      return `<tr>
        <td>${escapeHtml(row.host_name || row.id)}</td>
        <td>${row.humans}</td>
        <td>${row.alive}</td>
        <td>${row.tick}</td>
        <td>${
          joinable
            ? `<button type="button" data-join="${escapeHtml(row.id)}">Join</button>`
            : "full"
        }</td>
      </tr>`;
    })
    .join("");
}

async function refreshLobbies() {
  try {
    const response = await fetch("api/lobbies");
    const body = await response.json();
    renderLobbyList(body.lobbies || []);
  } catch (err) {
    showLobbyError(String(err));
  }
}

async function newGame() {
  showLobbyError("");
  const seedRaw = els.lobbySeed && els.lobbySeed.value;
  const payload = {};
  if (seedRaw !== "" && seedRaw != null) payload.seed = Number(seedRaw);
  const response = await fetch("api/lobbies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    showLobbyError("Could not create game");
    return;
  }
  const body = await response.json();
  location.search = `?lobby=${encodeURIComponent(body.id)}`;
}

function startLobby() {
  els.lobbyView.classList.remove("hidden");
  els.playView.classList.add("hidden");
  refreshLobbies();
  setInterval(refreshLobbies, 2000);
  els.newGame.addEventListener("click", () => {
    newGame().catch((err) => showLobbyError(String(err)));
  });
  els.lobbyRows.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-join]");
    if (!btn) return;
    location.search = `?lobby=${encodeURIComponent(btn.dataset.join)}`;
  });
}

function startPlay() {
  els.lobbyView.classList.add("hidden");
  els.playView.classList.remove("hidden");
  const client = connect({
    url: wsUrl,
    onSnapshot,
    onError,
    onClose,
  });
  send = client.send;
}

const params = new URLSearchParams(location.search);
if (params.get("lobby")) {
  startPlay();
} else {
  startLobby();
}

els.playpause.addEventListener("click", () => {
  const paused = snapshot?.clock?.mode === "pause";
  send({ op: "clock", mode: paused ? "play" : "pause" });
});

els.step.addEventListener("click", () => {
  if (!stepEnabled(snapshot)) return;
  send({ op: "clock", mode: "step" });
});

els.speeds.addEventListener("click", (ev) => {
  const btn = ev.target.closest("[data-speed]");
  if (!btn) return;
  const speed = Number(btn.dataset.speed);
  if (!Number.isFinite(speed) || !SPEEDS.includes(speed)) return;
  send({ op: "clock", speed });
});

els.timeoutS.addEventListener("change", () => {
  const seconds = Number(els.timeoutS.value);
  if (!Number.isFinite(seconds) || seconds < 0) return;
  send({ op: "clock", timeout_ms: seconds === 0 ? 0 : Math.round(seconds * 1000) });
});

els.panel.addEventListener("click", (ev) => {
  const btn = ev.target.closest("button");
  if (!btn || !els.panel.contains(btn)) return;
  if (btn.dataset.id != null) {
    const id = Number(btn.dataset.id);
    if (Number.isFinite(id)) handleSurvivorClick(id);
    return;
  }
  if (btn.dataset.act === "produce") {
    if (!actsEnabled(snapshot)) return;
    targeting = null;
    selectedId = null;
    send({ op: "act", action: "produce" });
    return;
  }
  if (btn.dataset.mode) {
    setTargeting(btn.dataset.mode);
    return;
  }
  if (btn.dataset.confirm) {
    confirmTargetedAct();
    return;
  }
  if (btn.dataset.release) {
    send({ op: "release" });
  }
});

els.banner.addEventListener("click", (ev) => {
  const btn = ev.target.closest("[data-op]");
  if (!btn) return;
  if (btn.dataset.op === "reset") {
    send({ op: "reset" });
    return;
  }
  if (btn.dataset.op === "auto") {
    const id = pickSuccessor(livingList());
    if (id == null) return;
    send({ op: "possess", id });
  }
});

render();
