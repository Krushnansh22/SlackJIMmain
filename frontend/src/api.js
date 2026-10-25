async function request(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch {}
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return res.json();
}

export const api = {
  list: () => request("/api/tickets"),
  create: (creator_name, raw_transcription) =>
    request("/api/tickets", {
      method: "POST",
      body: JSON.stringify({ creator_name, raw_transcription }),
    }),
  claim: (id, name) =>
    request(`/api/tickets/${id}/claim`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  resolve: (id, name) =>
    request(`/api/tickets/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
};
