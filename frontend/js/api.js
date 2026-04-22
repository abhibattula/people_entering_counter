const BASE = "";

async function _req(method, path, opts = {}) {
  const res = await fetch(BASE + path, { method, ...opts });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(body.detail || res.statusText), { status: res.status });
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── Profiles ─────────────────────────────────────────────────────────────
export const getProfiles    = ()     => _req("GET",    "/api/profiles");
export const getProfile     = (id)   => _req("GET",    `/api/profiles/${id}`);
export const createProfile  = (data) => _req("POST",   "/api/profiles", { headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
export const deleteProfile  = (id)   => _req("DELETE", `/api/profiles/${id}`);
export const exportProfile  = (id)   => fetch(`/api/profiles/${id}/export`);

export async function importProfile(file) {
  const fd = new FormData();
  fd.append("file", file);
  return _req("POST", "/api/profiles/import", { body: fd });
}

// ── Sessions ──────────────────────────────────────────────────────────────
export const startSession   = (profileId) => _req("POST",  "/api/sessions/start", { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile_id: profileId }) });
export const endSession     = (id)        => _req("POST",  `/api/sessions/${id}/end`);
export const pauseSession   = (id)        => _req("POST",  `/api/sessions/${id}/pause`);
export const resumeSession  = (id)        => _req("POST",  `/api/sessions/${id}/resume`);
export const getEvents      = (id)        => _req("GET",   `/api/sessions/${id}/events`);
export const getSessions    = (profileId) => _req("GET",   `/api/sessions?profile_id=${profileId}`);
export const exportSession  = (id)        => fetch(`/api/sessions/${id}/export`);
export const flipDirection  = (id)        => _req("PATCH", `/api/profiles/${id}/direction`);

// ── Calibration ───────────────────────────────────────────────────────────
export async function startCalibration(frames, mode) {
  const fd = new FormData();
  frames.forEach((blob, i) => fd.append("frames", blob, `frame${i}.jpg`));
  fd.append("mode", mode);
  return _req("POST", "/api/calibrate/frames", { body: fd });
}

export async function retryCalibration(frames, mode) {
  const fd = new FormData();
  frames.forEach((blob, i) => fd.append("frames", blob, `frame${i}.jpg`));
  fd.append("mode", mode);
  return _req("POST", "/api/calibrate/retry", { body: fd });
}

// ── System ────────────────────────────────────────────────────────────────
export const getHealth  = () => _req("GET", "/api/health");
export const getCameras = () => _req("GET", "/api/cameras");
