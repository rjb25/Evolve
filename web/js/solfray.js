export const VERSION = "1.0.0"; // must match web/solfray-playable.json

const RESULT_MAX = 500;

let sf = null;
let lastSnap = null;
let offered = false;

export async function instanceSlug(instance) {
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(String(instance ?? ""))
  );
  return Array.from(new Uint8Array(buf), (b) =>
    b.toString(16).padStart(2, "0")
  )
    .join("")
    .slice(0, 16);
}

function isExtinct(snapshot) {
  if (!snapshot) return false;
  if (snapshot.clock?.mode === "extinct") return true;
  return (snapshot.population || 0) === 0;
}

export function resultText(snapshot) {
  if (!snapshot) return "";
  const humans = (snapshot.humans || []).length;
  const tick = snapshot.tick ?? 0;
  const lines = [`Evolution · ${humans} humans · tick ${tick}`, "extinct"];
  const slug = sf?.server?.slug;
  const id = sf?.thread?.root_id;
  if (slug && id) lines.push(`solfray.com/s/${slug}/t/${id}`);
  const text = lines.join("\n");
  return text.length > RESULT_MAX ? text.slice(0, RESULT_MAX) : text;
}

export function offerResult(snapshot) {
  lastSnap = snapshot || null;
  if (snapshot && (snapshot.tick || 0) === 0) offered = false;
  if (!snapshot || !isExtinct(snapshot) || offered) return;
  offered = true;
  const text = resultText(snapshot);
  if (sf && typeof sf.result === "function") sf.result(text);
}

export function copyResult() {
  const text = resultText(lastSnap);
  const write = navigator.clipboard && navigator.clipboard.writeText;
  if (!text || typeof write !== "function") return;
  navigator.clipboard.writeText(text).catch(() => {});
}

function captureBoard(snapshot) {
  if (!snapshot) return null;
  const rows = snapshot.survivors || [];
  const pad = 16;
  const lineH = 20;
  const canvas = document.createElement("canvas");
  canvas.width = 480;
  canvas.height = 360;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.fillStyle = "#101418";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#e7edf2";
  ctx.font = "16px monospace";
  ctx.fillText("Evolution", pad, pad + 14);
  ctx.font = "13px monospace";
  ctx.fillStyle = "#8b97a3";
  const humans = (snapshot.humans || []).length;
  ctx.fillText(`tick ${snapshot.tick ?? "—"}  humans ${humans}`, pad, pad + 36);
  ctx.fillStyle = "#e7edf2";
  if (!rows.length) {
    ctx.fillStyle = "#8b97a3";
    ctx.fillText("extinct", pad, pad + 64);
    return canvas;
  }
  const maxRows = Math.floor((canvas.height - pad - 56) / lineH);
  rows.slice(0, maxRows).forEach((row, i) => {
    const name = String(row.name || "");
    const hp = row.health ?? 0;
    ctx.fillStyle = row.alive ? "#e7edf2" : "#8b97a3";
    ctx.fillText(`${name}  ${hp}`, pad, pad + 64 + i * lineH);
  });
  return canvas;
}

export async function bootHosted(hostedSf) {
  sf = hostedSf || null;
  lastSnap = null;
  offered = false;
  const slug = await instanceSlug(sf.instance);
  const q = new URLSearchParams(location.search);
  q.set("lobby", `sf-${slug}`);
  history.replaceState(null, "", `${location.pathname}?${q}`);
  if (sf && typeof sf.onScreenshot === "function") {
    sf.onScreenshot(() => captureBoard(lastSnap));
  }
}
