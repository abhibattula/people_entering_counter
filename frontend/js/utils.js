// ── Canvas drawing helpers ────────────────────────────────────────────────

export function drawPolygon(ctx, points, colour = "#8000ff", dashed = true) {
  ctx.save();
  ctx.strokeStyle = colour;
  ctx.lineWidth = 2;
  if (dashed) ctx.setLineDash([6, 4]);
  ctx.beginPath();
  points.forEach(([x, y], i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y));
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
}

export function drawLine(ctx, line, colour = "#ffff00", dashed = true) {
  ctx.save();
  ctx.strokeStyle = colour;
  ctx.lineWidth = 2;
  if (dashed) ctx.setLineDash([8, 4]);
  ctx.beginPath();
  ctx.moveTo(line.x1, line.y1);
  ctx.lineTo(line.x2, line.y2);
  ctx.stroke();
  ctx.restore();
}

export function drawArrow(ctx, x, y, direction, colour = "#00c800") {
  const len = 30;
  const map = { up: [0, -len], down: [0, len], left: [-len, 0], right: [len, 0] };
  const [dx, dy] = map[direction] || [0, -len];
  ctx.save();
  ctx.strokeStyle = colour;
  ctx.fillStyle = colour;
  ctx.lineWidth = 2;
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + dx, y + dy);
  ctx.stroke();
  // arrowhead
  const angle = Math.atan2(dy, dx);
  ctx.beginPath();
  ctx.moveTo(x + dx, y + dy);
  ctx.lineTo(x + dx - 10 * Math.cos(angle - 0.4), y + dy - 10 * Math.sin(angle - 0.4));
  ctx.lineTo(x + dx - 10 * Math.cos(angle + 0.4), y + dy - 10 * Math.sin(angle + 0.4));
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

export function drawBoundingBox(ctx, box, label = "", colour = "#00ff00") {
  const [x1, y1, x2, y2] = box;
  ctx.save();
  ctx.strokeStyle = colour;
  ctx.lineWidth = 2;
  ctx.setLineDash([]);
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  if (label) {
    ctx.fillStyle = colour;
    ctx.font = "12px monospace";
    ctx.fillText(label, x1 + 2, y1 - 4);
  }
  ctx.restore();
}

// ── Quality badge renderer ────────────────────────────────────────────────

export function renderQualityBadges(container, qualityCheck) {
  const items = [
    {
      key: "door_fully_visible",
      label: "Door visible",
      value: qualityCheck.door_fully_visible ? "Yes" : "No",
      pass: qualityCheck.door_fully_visible,
    },
    {
      key: "lighting_acceptable",
      label: "Lighting",
      value: qualityCheck.lighting_acceptable ? "OK" : "Poor",
      pass: qualityCheck.lighting_acceptable,
    },
    {
      key: "crowding_risk",
      label: "Crowding risk",
      value: qualityCheck.crowding_risk,
      pass: qualityCheck.crowding_risk === "low",
      warn: qualityCheck.crowding_risk === "medium",
    },
    {
      key: "camera_adjustment",
      label: "Camera distance",
      value: qualityCheck.camera_adjustment === "keep"
        ? "Good"
        : qualityCheck.camera_adjustment === "closer"
        ? "Move closer"
        : "Move farther",
      pass: qualityCheck.camera_adjustment === "keep",
      warn: false,
    },
  ];

  container.innerHTML = "";
  container.className = "quality-grid";
  items.forEach(({ label, value, pass, warn }) => {
    const badge = document.createElement("div");
    badge.className = `quality-badge ${pass ? "pass" : warn ? "warn" : "fail"}`;
    badge.innerHTML = `
      <span class="icon">${pass ? "✅" : warn ? "⚠️" : "❌"}</span>
      <div>
        <div class="label">${label}</div>
        <div class="value">${value}</div>
      </div>`;
    container.appendChild(badge);
  });
}

// ── Misc helpers ──────────────────────────────────────────────────────────

export function formatTime(isoStr) {
  return new Date(isoStr).toLocaleTimeString();
}

export function triggerDownload(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export async function blobToJpeg(canvas) {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
}
