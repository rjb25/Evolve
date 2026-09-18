export function deriveWsUrl() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/Evolution/ws${location.search}`;
}

export function connect({ url, onSnapshot, onError, onClose } = {}) {
  const wsUrl = url || deriveWsUrl();
  const ws = new WebSocket(wsUrl);
  const queue = [];

  ws.addEventListener("open", () => {
    while (queue.length && ws.readyState === WebSocket.OPEN) {
      ws.send(queue.shift());
    }
  });

  ws.addEventListener("message", (ev) => {
    let data;
    try {
      data = JSON.parse(ev.data);
    } catch {
      onError?.({ v: 1, error: "invalid_json", detail: "malformed JSON" });
      return;
    }
    if (data && typeof data === "object" && data.error) {
      onError?.(data);
      return;
    }
    onSnapshot?.(data);
  });

  ws.addEventListener("close", (ev) => {
    onClose?.(ev);
  });

  function send(payload) {
    const raw = JSON.stringify(payload);
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(raw);
      return;
    }
    if (ws.readyState === WebSocket.CONNECTING) {
      queue.push(raw);
    }
  }

  function close() {
    queue.length = 0;
    if (
      ws.readyState === WebSocket.OPEN ||
      ws.readyState === WebSocket.CONNECTING
    ) {
      ws.close();
    }
  }

  return { send, close };
}
