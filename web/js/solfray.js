export const VERSION = "1.0.0"; // must match web/solfray-playable.json

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

export async function bootHosted(sf) {
  const slug = await instanceSlug(sf.instance);
  const q = new URLSearchParams(location.search);
  q.set("lobby", `sf-${slug}`);
  history.replaceState(null, "", `${location.pathname}?${q}`);
}
