import { startCalibration, retryCalibration, createProfile } from "/js/api.js";
import { drawPolygon, drawLine, drawArrow, renderQualityBadges, blobToJpeg } from "/js/utils.js";

// ── State ─────────────────────────────────────────────────────────────────
let stream = null;
let currentStep = 1;
const TOTAL_STEPS = 8;

let capturedFrames = [];    // Blob[]
const PHOTO_INSTRUCTIONS = [
  "Centre view — fill the doorway",
  "Slightly left",
  "Slightly right",
  "Tilt up slightly",
  "Final position — this is the counting view",
];
let photoIndex = 0;

let qualityResult = null;
let proposalResult = null;
let flippedDirection = null;
let doorRandomlyOpens = false;

// Manual draw state
let drawPoints = [];        // [[x,y],...]
let lineY = null;
let dragging = null;
let drawBgImage = null;

// ── DOM refs ──────────────────────────────────────────────────────────────
const steps = Array.from({ length: TOTAL_STEPS }, (_, i) => document.getElementById(`step-${i + 1}`));
const dots  = document.getElementById("step-dots");

// ── Step navigation ───────────────────────────────────────────────────────

function showStep(n) {
  steps.forEach((s, i) => s.classList.toggle("active", i + 1 === n));
  currentStep = n;
  renderDots();
}

const STEP_NAMES = ["Camera", "Preview", "Capture", "Quality", "Boundary", "Draw", "Door", "Save"];

function renderDots() {
  dots.innerHTML = STEP_NAMES.map((name, i) => {
    const n = i + 1;
    const cls = n < currentStep ? "done" : n === currentStep ? "current" : "";
    const inner = n < currentStep
      ? `<span style="font-size:.55rem;color:#fff">✓</span>`
      : n === currentStep
        ? `<span class="prog-inner-dot"></span>`
        : "";
    const connector = i < TOTAL_STEPS - 1
      ? `<div class="prog-connector${n < currentStep ? " done" : ""}"></div>`
      : "";
    return `
      <div class="prog-step-wrap">
        <div class="prog-dot ${cls}">${inner}</div>
        <div class="prog-label ${cls}">${name}</div>
      </div>
      ${connector}`;
  }).join("");
}

// ── Step 1: Camera permission ─────────────────────────────────────────────

document.getElementById("btn-allow-camera").addEventListener("click", async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
    document.getElementById("preview").srcObject = stream;
    document.getElementById("capture-preview").srcObject = stream;
    showStep(2);
  } catch (e) {
    const permError = document.getElementById("permission-error");
    if (e.name === "NotAllowedError") {
      permError.innerHTML =
        "Camera access was denied. To re-enable:<br>" +
        "<strong>Chrome:</strong> Click the camera icon in the address bar → Allow.<br>" +
        "<strong>Firefox:</strong> Click the shield icon → Remove block.<br>" +
        "<strong>Safari:</strong> Safari menu → Settings for this website → Camera → Allow.";
    } else {
      permError.innerHTML = "Camera error: " + e.message;
    }
    permError.classList.remove("hidden");
  }
});

// ── Step 2: Preview ───────────────────────────────────────────────────────

document.getElementById("btn-to-mode").addEventListener("click", () => {
  photoIndex = 0;
  startPhotoCapture();
  showStep(3);
});

// ── Step 3: Capture ───────────────────────────────────────────────────────

function startPhotoCapture() {
  capturedFrames = [];
  document.getElementById("thumb-strip").innerHTML = "";
  document.getElementById("btn-capture").classList.remove("hidden");
  nextPhotoInstruction();
}

function nextPhotoInstruction() {
  document.getElementById("capture-heading").textContent = `Photo ${photoIndex + 1} of 5`;
  document.getElementById("capture-instruction").textContent = PHOTO_INSTRUCTIONS[photoIndex];
}

document.getElementById("btn-capture").addEventListener("click", async () => {
  const video = document.getElementById("capture-preview");
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  canvas.getContext("2d").drawImage(video, 0, 0);
  const blob = await blobToJpeg(canvas);
  capturedFrames.push(blob);

  // show thumbnail
  const img = document.createElement("img");
  img.src = URL.createObjectURL(blob);
  img.classList.add("captured");
  document.getElementById("thumb-strip").appendChild(img);

  photoIndex++;
  if (photoIndex < 5) {
    nextPhotoInstruction();
  } else {
    document.getElementById("btn-capture").classList.add("hidden");
    await submitFrames();
  }
});

async function submitFrames() {
  document.getElementById("capture-instruction").textContent = "Analysing frames…";
  try {
    const resp = await startCalibration(capturedFrames, "photo");
    qualityResult = resp.quality_check;
    proposalResult = resp.proposal;
    showQualityStep();
  } catch (e) {
    document.getElementById("capture-instruction").textContent = "Error: " + e.message + " — try again";
    document.getElementById("btn-capture").classList.remove("hidden");
    photoIndex = 0; startPhotoCapture();
  }
}

// ── Step 4: Quality check ─────────────────────────────────────────────────

function showQualityStep() {
  renderQualityBadges(document.getElementById("quality-badges"), qualityResult);
  const critical = !qualityResult.door_fully_visible || !qualityResult.lighting_acceptable;
  document.getElementById("btn-recapture").style.display = critical ? "" : "none";
  showStep(4);
}

document.getElementById("btn-recapture").addEventListener("click", () => {
  photoIndex = 0; capturedFrames = [];
  startPhotoCapture(); showStep(3);
});

document.getElementById("btn-continue-anyway").addEventListener("click", () => showProposalStep());

// ── Step 5: Proposal ──────────────────────────────────────────────────────

function showProposalStep() {
  flippedDirection = null;
  const canvas = document.getElementById("proposal-canvas");
  const img = new Image();
  img.onload = () => {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
    drawPolygon(ctx, proposalResult.roi_polygon, "#8000ff");
    drawLine(ctx, proposalResult.counting_line, "#ffff00");
    const mx = (proposalResult.counting_line.x1 + proposalResult.counting_line.x2) / 2;
    const my = proposalResult.counting_line.y1;
    drawArrow(ctx, mx, my, proposalResult.inside_direction);
  };
  img.src = "data:image/jpeg;base64," + proposalResult.best_frame_b64;

  document.getElementById("btn-draw-manual").classList.toggle(
    "hidden", !proposalResult.manual_fallback_available
  );
  showStep(5);
}

document.getElementById("btn-flip-direction").addEventListener("click", () => {
  const FLIP = { up: "down", down: "up", left: "right", right: "left" };
  proposalResult.inside_direction = FLIP[proposalResult.inside_direction] || proposalResult.inside_direction;
  flippedDirection = proposalResult.inside_direction;
  showProposalStep();
});

document.getElementById("btn-accept-proposal").addEventListener("click", () => showStep(7));

document.getElementById("btn-reject-proposal").addEventListener("click", async () => {
  try {
    const resp = await retryCalibration(capturedFrames, "photo");
    qualityResult = resp.quality_check;
    proposalResult = resp.proposal;
    showProposalStep();
  } catch (e) {
    if (e.status === 429) {
      document.getElementById("btn-draw-manual").classList.remove("hidden");
      alert("Maximum auto-proposals reached. Please draw manually.");
    }
  }
});

document.getElementById("btn-draw-manual").addEventListener("click", () => startManualDraw());

// ── Step 6: Manual draw ───────────────────────────────────────────────────

function startManualDraw() {
  drawPoints = []; lineY = null; drawBgImage = null;
  document.getElementById("draw-progress").textContent = "Tap corner 1 of 4";
  document.getElementById("btn-save-draw").disabled = true;
  const canvas = document.getElementById("draw-canvas");
  const img = new Image();
  img.onload = () => {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    drawBgImage = img;
    redrawManual(canvas);
  };
  img.src = "data:image/jpeg;base64," + proposalResult.best_frame_b64;
  showStep(6);
}

document.getElementById("draw-canvas").addEventListener("click", (e) => {
  const canvas = document.getElementById("draw-canvas");
  const rect = canvas.getBoundingClientRect();
  const sx = canvas.width / rect.width;
  const sy = canvas.height / rect.height;
  if (drawPoints.length < 4) {
    drawPoints.push([Math.round((e.clientX - rect.left) * sx), Math.round((e.clientY - rect.top) * sy)]);
    if (drawPoints.length === 4) {
      lineY = Math.round(drawPoints.reduce((s, p) => s + p[1], 0) / 4);
      document.getElementById("btn-save-draw").disabled = false;
      document.getElementById("draw-progress").textContent = "All corners placed — click Save →";
    } else {
      document.getElementById("draw-progress").textContent = `Tap corner ${drawPoints.length + 1} of 4`;
    }
    redrawManual(canvas);
  }
});

function redrawManual(canvas) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (drawBgImage) ctx.drawImage(drawBgImage, 0, 0);

  if (drawPoints.length === 4) {
    drawPolygon(ctx, drawPoints, "#8000ff");
    const xs = drawPoints.map(p => p[0]);
    const line = { x1: Math.min(...xs), y1: lineY, x2: Math.max(...xs), y2: lineY };
    drawLine(ctx, line, "#ffff00");
  } else {
    drawPoints.forEach(([x, y], idx) => {
      ctx.beginPath();
      ctx.arc(x, y, 14, 0, Math.PI * 2);
      ctx.fillStyle = "white";
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x, y, 12, 0, Math.PI * 2);
      ctx.fillStyle = "#8000ff";
      ctx.fill();
      ctx.fillStyle = "white";
      ctx.font = "bold 14px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(idx + 1), x, y);
    });
  }
}

document.getElementById("btn-reset-draw").addEventListener("click", () => {
  drawPoints = []; lineY = null;
  document.getElementById("btn-save-draw").disabled = true;
  startManualDraw();
});

document.getElementById("btn-save-draw").addEventListener("click", () => {
  const xs = drawPoints.map(p => p[0]);
  const mid_y = lineY;
  proposalResult = {
    ...proposalResult,
    roi_polygon: drawPoints,
    counting_line: { x1: Math.min(...xs), y1: mid_y, x2: Math.max(...xs), y2: mid_y },
  };
  showStep(7);
});

// ── Step 7: Door behaviour ────────────────────────────────────────────────

document.getElementById("btn-door-no").addEventListener("click", () => { doorRandomlyOpens = false; showStep(8); });
document.getElementById("btn-door-yes").addEventListener("click", () => { doorRandomlyOpens = true; showStep(8); });

// ── Step 8: Save ──────────────────────────────────────────────────────────

document.getElementById("btn-save").addEventListener("click", async () => {
  const name = document.getElementById("profile-name").value.trim();
  if (!name) { document.getElementById("save-error").textContent = "Please enter a profile name."; document.getElementById("save-error").classList.remove("hidden"); return; }

  const video = document.getElementById("capture-preview");
  const body = {
    name,
    camera_index: 0,
    capture_mode: "photo",
    frame_width: video.videoWidth || 1280,
    frame_height: video.videoHeight || 720,
    roi_polygon: proposalResult.roi_polygon,
    counting_line: proposalResult.counting_line,
    inside_direction: proposalResult.inside_direction,
    door_randomly_opens: doorRandomlyOpens,
    quality_check: qualityResult || { door_fully_visible: true, lighting_acceptable: true, crowding_risk: "low", camera_adjustment: "keep" },
  };

  try {
    const { id } = await createProfile(body);
    // Release browser camera before Python/OpenCV takes over (constitution Principle IV)
    if (stream) stream.getTracks().forEach(t => t.stop());
    // Wait 1 s for the OS to fully release the camera handle (Windows timing)
    await new Promise(r => setTimeout(r, 1000));
    location.href = `/count.html?profile_id=${id}`;
  } catch (e) {
    const err = document.getElementById("save-error");
    err.textContent = e.message;
    err.classList.remove("hidden");
  }
});

// Boot
showStep(1);
