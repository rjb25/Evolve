import { escapeHtml } from "./board.js";

const KINDS = new Set([
  "produce",
  "deal",
  "list",
  "unlist",
  "relate",
  "death",
  "possess",
  "release",
  "reset",
]);

function namesFrom(snapshot) {
  const names = new Map();
  for (const row of snapshot?.survivors || []) {
    if (row && row.id != null && row.name) names.set(row.id, row.name);
  }
  return names;
}

function label(id, names, fallback) {
  if (fallback) return String(fallback);
  if (id == null) return "?";
  if (names.has(id)) return names.get(id);
  return `#${id}`;
}

function formatEvent(ev, names) {
  const actor = label(ev.actor, names, ev.kind === "death" ? ev.name : null);
  const target = ev.target != null ? label(ev.target, names) : null;
  switch (ev.kind) {
    case "produce":
      return `${label(ev.actor, names, ev.name)} produced`;
    case "list": {
      const give = ev.give || "?";
      const get = ev.get || "?";
      return `${actor} listed ${give}→${get}`;
    }
    case "unlist": {
      const give = ev.give || "?";
      const get = ev.get || "?";
      return `${actor} dropped ${give}→${get}`;
    }
    case "deal": {
      const give = ev.give || "?";
      const get = ev.get || "?";
      const withWhom = target != null ? ` with ${target}` : "";
      return `${actor} deal ${give}→${get}${withWhom} accepted`;
    }
    case "relate":
      return target != null ? `${actor} related ${target}` : `${actor} related`;
    case "death":
      return `${ev.name || actor} died`;
    case "possess":
      return ev.actor != null ? `possessed ${actor}` : "possess";
    case "release":
      return "released control";
    case "reset":
      return "reset";
    default:
      return ev.kind;
  }
}

function rowHtml(ev, text) {
  return `<li data-event-id="${ev.event_id}" data-kind="${escapeHtml(ev.kind)}">
    <span class="tick">t${ev.tick}</span>
    <span class="msg">${escapeHtml(text)}</span>
  </li>`;
}

export function renderLog(root, snapshot) {
  if (!root) return;
  if (!root._logSeen) root._logSeen = new Set();
  const seen = root._logSeen;
  const names = namesFrom(snapshot);
  const incoming = (snapshot?.events || []).filter(
    (ev) => ev && Number.isFinite(ev.event_id) && KINDS.has(ev.kind)
  );

  // Wipe on a new reset so old-run rows cannot linger and a colliding id cannot hide it.
  let events = incoming;
  const resetEv = [...incoming].reverse().find((ev) => ev.kind === "reset");
  if (resetEv) {
    const existing = root.querySelector(`[data-event-id="${resetEv.event_id}"]`);
    if (!existing || existing.dataset.kind !== "reset") {
      seen.clear();
      root.innerHTML = "";
      const idx = incoming.findIndex((ev) => ev.event_id === resetEv.event_id);
      if (idx >= 0) events = incoming.slice(idx);
    }
  }

  for (const ev of events) {
    if (seen.has(ev.event_id)) continue;
    seen.add(ev.event_id);
    root.insertAdjacentHTML("afterbegin", rowHtml(ev, formatEvent(ev, names)));
  }

  const incomingIds = new Set(events.map((ev) => ev.event_id));
  for (const li of [...root.children]) {
    const id = Number(li.dataset.eventId);
    if (incomingIds.has(id)) continue;
    seen.delete(id);
    li.remove();
  }
}
