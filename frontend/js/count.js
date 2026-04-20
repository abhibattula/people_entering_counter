import { getProfile, startSession, endSession, pauseSession, resumeSession, exportSession } from "/js/api.js";
import { formatTime } from "/js/utils.js";

const params = new URLSearchParams(location.search);
const profileId = params.get("profile_id");
if (!profileId) location.href = "/";

let sessionId = null;
let inCount = 0, outCount = 0;
let paused = false;
let ws = null;
let wsRetries = 0;
const MAX_WS_RETRIES = 5;

const streamImg      = document.getElementById("stream");
const streamError    = document.getElementById("stream-error");
const countIn        = document.getElementById("count-in");
const countOut       = document.getElementById("count-out");
const countOcc       = document.getElementById("count-occ");
const eventsLog      = document.getElementById("events-log");
const profileName    = document.getElementById("profile-name");
const doorBanner     = document.getElementById("door-banner");
const reconnBanner   = document.getElementById("reconnect-banner");
const btnPause       = document.getElementById("btn-pause");
const btnStop        = document.getElementById("btn-stop");
const btnExport      = document.getElementById("btn-export");
const btnReloadStream = document.getElementById("btn-reload-stream");

// ── Init ─────────────────────────────────────────────────────────────────

async function init() {
  const profile = await getProfile(profileId).catch(() => null);
  if (!profile) { alert("Profile not found"); location.href = "/"; return; }

  profileName.textContent = profile.name;
  if (profile.door_randomly_opens) doorBanner.classList.remove("hidden");

  const session = await startSession(profileId).catch(e => { alert(e.message); return null; });
  if (!session) return;
  sessionId = session.session_id;

  startStream();
  connectWs();
}

// ── MJPEG stream ──────────────────────────────────────────────────────────

function startStream() {
  streamImg.src = `/stream?profile_id=${profileId}&t=${Date.now()}`;
  streamImg.onerror = onStreamError;
  streamImg.onload = () => streamError.classList.add("hidden");
}

function onStreamError() {
  streamError.classList.remove("hidden");
}

btnReloadStream.addEventListener("click", () => {
  streamError.classList.add("hidden");
  setTimeout(startStream, 500);
});

// ── WebSocket ─────────────────────────────────────────────────────────────

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/counts?profile_id=${profileId}`);

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "ping") return;
    if (data.direction === "in")  inCount++;
    if (data.direction === "out") outCount++;
    countIn.textContent  = inCount;
    countOut.textContent = outCount;
    countOcc.textContent = Math.max(0, inCount - outCount);
    addEventRow(data);
    wsRetries = 0;
  };

  ws.onclose = ws.onerror = () => {
    if (wsRetries < MAX_WS_RETRIES) {
      wsRetries++;
      reconnBanner.classList.remove("hidden");
      setTimeout(connectWs, 3000);
    }
  };

  ws.onopen = () => reconnBanner.classList.add("hidden");
}

function addEventRow(event) {
  const row = document.createElement("div");
  row.className = `event-row ${event.direction}`;
  row.innerHTML = `<span>${event.direction === "in" ? "↑ IN" : "↓ OUT"}</span><span>${formatTime(event.timestamp)}</span>`;
  eventsLog.prepend(row);
  if (eventsLog.children.length > 50) eventsLog.lastChild.remove();
}

// ── Controls ──────────────────────────────────────────────────────────────

btnPause.addEventListener("click", async () => {
  if (!sessionId) return;
  if (!paused) {
    await pauseSession(sessionId).catch(console.error);
    paused = true;
    btnPause.textContent = "▶ Resume";
    streamImg.style.opacity = "0.5";
    document.getElementById("live-dot").style.animationPlayState = "paused";
  } else {
    await resumeSession(sessionId).catch(console.error);
    paused = false;
    btnPause.textContent = "⏸ Pause";
    streamImg.style.opacity = "1";
    document.getElementById("live-dot").style.animationPlayState = "running";
  }
});

btnStop.addEventListener("click", async () => {
  if (!confirm("Stop this counting session?")) return;
  if (sessionId) await endSession(sessionId).catch(console.error);
  if (ws) ws.close(1001);
  streamImg.src = "";
  location.href = "/";
});

btnExport.addEventListener("click", async () => {
  if (!sessionId) return;
  const res = await exportSession(sessionId);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `session-${sessionId}.csv`;
  a.click(); URL.revokeObjectURL(url);
});

init();
