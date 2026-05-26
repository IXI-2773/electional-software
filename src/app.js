const form = document.querySelector("#electionForm");
const dateInput = document.querySelector("#dateInput");
const locationPresetInput = document.querySelector("#locationPresetInput");
const locationInput = document.querySelector("#locationInput");
const latitudeInput = document.querySelector("#latitudeInput");
const longitudeInput = document.querySelector("#longitudeInput");
const timezoneInput = document.querySelector("#timezoneInput");
const presetInput = document.querySelector("#presetInput");
const timeline = document.querySelector("#timeline");
const bestScore = document.querySelector("#bestScore");
const beneficCount = document.querySelector("#beneficCount");
const stressCount = document.querySelector("#stressCount");
const trackedCount = document.querySelector("#trackedCount");
const timezoneLabel = document.querySelector("#timezoneLabel");
const angularCount = document.querySelector("#angularCount");
const presetLabel = document.querySelector("#presetLabel");
const orbLabel = document.querySelector("#orbLabel");
const workspaceTitle = document.querySelector("#workspaceTitle");
const positionTimestamp = document.querySelector("#positionTimestamp");
const positionGrid = document.querySelector("#positionGrid");
const angleGrid = document.querySelector("#angleGrid");
const detectedGrid = document.querySelector("#detectedGrid");
const validationSource = document.querySelector("#validationSource");
const validationPanel = document.querySelector("#validationPanel");
const chartWheel = document.querySelector("#chartWheel");
const chartTitle = document.querySelector("#chartTitle");
const chartMeta = document.querySelector("#chartMeta");
const statusLocation = document.querySelector("#statusLocation");
const statusTime = document.querySelector("#statusTime");
const statusPreset = document.querySelector("#statusPreset");
const statusValidation = document.querySelector("#statusValidation");

dateInput.value = new Date().toISOString().slice(0, 10);

const ZODIAC_GLYPHS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"];
const PLANET_GLYPHS = {
  Sun: "☉",
  Moon: "☽",
  Mercury: "☿",
  Venus: "♀",
  Mars: "♂",
  Jupiter: "♃",
  Saturn: "♄",
  Uranus: "♅",
  Neptune: "♆",
  Pluto: "♇",
};
const ASPECT_COLORS = {
  conjunction: "#283047",
  trine: "#1c8f7a",
  sextile: "#2279a8",
  square: "#b54e64",
  opposition: "#8b3e8a",
};

function getFormState() {
  const data = new FormData(form);
  return {
    date: data.get("date"),
    time: data.get("time"),
    location: data.get("location"),
    latitude: Number(data.get("latitude")),
    longitude: Number(data.get("longitude")),
    timezone: data.get("timezone"),
    objective: data.get("objective"),
    presetId: data.get("presetId"),
    aspects: data.getAll("aspect"),
  };
}

function applyPresetSelection() {
  const preset = window.ElectionalPresets.getPreset(presetInput.value);
  const checkboxes = [...form.querySelectorAll('input[name="aspect"]')];

  checkboxes.forEach((checkbox) => {
    checkbox.checked = preset.aspectIds.includes(checkbox.value);
  });
}

function applyLocationPreset() {
  const preset = window.ElectionalTimezone.LOCATION_PRESETS[locationPresetInput.value];

  if (!preset) {
    return;
  }

  locationInput.value = preset.name;
  latitudeInput.value = preset.latitude;
  longitudeInput.value = preset.longitude;
  timezoneInput.value = preset.timezone;
}

function polarPoint(center, radius, degrees) {
  const radians = degrees * Math.PI / 180;
  return {
    x: center + radius * Math.cos(radians),
    y: center + radius * Math.sin(radians),
  };
}

function longitudeToWheelDegrees(longitude, ascendantLongitude) {
  return 180 - window.ElectionalEphemeris.normalizeDegrees(longitude - ascendantLongitude);
}

function annularSectorPath(center, innerRadius, outerRadius, startDegrees, endDegrees) {
  const startOuter = polarPoint(center, outerRadius, startDegrees);
  const endOuter = polarPoint(center, outerRadius, endDegrees);
  const startInner = polarPoint(center, innerRadius, endDegrees);
  const endInner = polarPoint(center, innerRadius, startDegrees);
  const largeArc = Math.abs(endDegrees - startDegrees) > 180 ? 1 : 0;

  return [
    `M ${startOuter.x.toFixed(2)} ${startOuter.y.toFixed(2)}`,
    `A ${outerRadius} ${outerRadius} 0 ${largeArc} 1 ${endOuter.x.toFixed(2)} ${endOuter.y.toFixed(2)}`,
    `L ${startInner.x.toFixed(2)} ${startInner.y.toFixed(2)}`,
    `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${endInner.x.toFixed(2)} ${endInner.y.toFixed(2)}`,
    "Z",
  ].join(" ");
}

function lineForLongitude(longitude, ascendantLongitude, innerRadius, outerRadius, className) {
  const center = 300;
  const degrees = longitudeToWheelDegrees(longitude, ascendantLongitude);
  const inner = polarPoint(center, innerRadius, degrees);
  const outer = polarPoint(center, outerRadius, degrees);
  return `<line class="${className}" x1="${inner.x.toFixed(2)}" y1="${inner.y.toFixed(2)}" x2="${outer.x.toFixed(2)}" y2="${outer.y.toFixed(2)}" />`;
}

function renderChartWheel(snapshot) {
  const center = 300;
  const ascendant = snapshot.angles.find((angle) => angle.id === "asc");
  const zodiacOuter = 282;
  const zodiacInner = 238;
  const houseOuter = 238;
  const houseInner = 150;
  const aspectRadius = 118;
  const planetRadius = 207;

  const zodiacSegments = ZODIAC_GLYPHS.map((glyph, index) => {
    const start = longitudeToWheelDegrees(index * 30, ascendant.longitude);
    const end = longitudeToWheelDegrees((index + 1) * 30, ascendant.longitude);
    const labelPoint = polarPoint(center, 260, longitudeToWheelDegrees(index * 30 + 15, ascendant.longitude));
    return `
      <path class="zodiac-sector zodiac-${index}" d="${annularSectorPath(center, zodiacInner, zodiacOuter, end, start)}" />
      <text class="zodiac-label" x="${labelPoint.x.toFixed(2)}" y="${labelPoint.y.toFixed(2)}">${glyph}</text>
    `;
  }).join("");

  const houseSegments = Array.from({ length: 12 }, (_, index) => {
    const start = ascendant.longitude + index * 30;
    const end = ascendant.longitude + (index + 1) * 30;
    const labelPoint = polarPoint(center, 183, longitudeToWheelDegrees(start + 15, ascendant.longitude));
    return `
      <path class="house-sector house-${index}" d="${annularSectorPath(center, houseInner, houseOuter, longitudeToWheelDegrees(end, ascendant.longitude), longitudeToWheelDegrees(start, ascendant.longitude))}" />
      <text class="house-label" x="${labelPoint.x.toFixed(2)}" y="${labelPoint.y.toFixed(2)}">${index + 1}</text>
    `;
  }).join("");

  const signLines = Array.from({ length: 12 }, (_, index) => {
    return lineForLongitude(index * 30, ascendant.longitude, zodiacInner, zodiacOuter, "sign-line");
  }).join("");

  const houseLines = Array.from({ length: 12 }, (_, index) => {
    return lineForLongitude(ascendant.longitude + index * 30, ascendant.longitude, houseInner, houseOuter, "house-line");
  }).join("");

  const angleLines = snapshot.angles.map((angle) => {
    return lineForLongitude(angle.longitude, ascendant.longitude, 88, zodiacOuter, `angle-line ${angle.id}`);
  }).join("");

  const angleLabels = snapshot.angles.map((angle) => {
    const point = polarPoint(center, 248, longitudeToWheelDegrees(angle.longitude, ascendant.longitude));
    return `<text class="angle-label ${angle.id}" x="${point.x.toFixed(2)}" y="${point.y.toFixed(2)}">${angle.shortName}</text>`;
  }).join("");

  const aspectLines = snapshot.detectedAspects.map((aspect) => {
    const first = snapshot.positions.find((planet) => planet.name === aspect.bodies[0]);
    const second = snapshot.positions.find((planet) => planet.name === aspect.bodies[1]);
    const firstPoint = polarPoint(center, aspectRadius, longitudeToWheelDegrees(first.longitude, ascendant.longitude));
    const secondPoint = polarPoint(center, aspectRadius, longitudeToWheelDegrees(second.longitude, ascendant.longitude));
    const color = ASPECT_COLORS[aspect.aspectId] || "#8b7c6f";
    return `<line class="aspect-line" style="--aspect-color:${color}" x1="${firstPoint.x.toFixed(2)}" y1="${firstPoint.y.toFixed(2)}" x2="${secondPoint.x.toFixed(2)}" y2="${secondPoint.y.toFixed(2)}" />`;
  }).join("");

  const planetMarkers = snapshot.positions.map((planet) => {
    const point = polarPoint(center, planetRadius, longitudeToWheelDegrees(planet.longitude, ascendant.longitude));
    const tickStart = polarPoint(center, 226, longitudeToWheelDegrees(planet.longitude, ascendant.longitude));
    const tickEnd = polarPoint(center, 238, longitudeToWheelDegrees(planet.longitude, ascendant.longitude));
    return `
      <line class="planet-tick" x1="${tickStart.x.toFixed(2)}" y1="${tickStart.y.toFixed(2)}" x2="${tickEnd.x.toFixed(2)}" y2="${tickEnd.y.toFixed(2)}" />
      <g class="planet-marker ${planet.isAngular ? "angular" : ""}" transform="translate(${point.x.toFixed(2)} ${point.y.toFixed(2)})">
        <circle r="12" />
        <text y="5">${PLANET_GLYPHS[planet.name] || planet.name.slice(0, 2)}</text>
      </g>
    `;
  }).join("");

  chartWheel.innerHTML = `
    <svg class="wheel-svg" viewBox="0 0 600 600" role="img" aria-label="Electional astrology chart wheel">
      <circle class="outer-disc" cx="${center}" cy="${center}" r="${zodiacOuter}" />
      ${zodiacSegments}
      ${signLines}
      ${houseSegments}
      ${houseLines}
      <circle class="aspect-disc" cx="${center}" cy="${center}" r="${aspectRadius}" />
      ${aspectLines}
      ${angleLines}
      ${planetMarkers}
      ${angleLabels}
      <circle class="center-disc" cx="${center}" cy="${center}" r="75" />
      <text class="center-title" x="${center}" y="${center - 6}">Election</text>
      <text class="center-subtitle" x="${center}" y="${center + 17}">${window.ElectionalEphemeris.engine}</text>
    </svg>
  `;
}

function renderTimeline(windows) {
  timeline.innerHTML = windows.map((transitWindow, index) => {
    const tags = transitWindow.detectedAspects
      .slice(0, 3)
      .map((aspect) => {
        const tone = aspect.tone === "stress" ? " stress" : "";
        return `<span class="tag${tone}">${aspect.label}</span>`;
      })
      .join("");

    return `
      <article class="timeline-card ${index === 0 ? "selected" : ""}">
        <div class="timeline-time">${transitWindow.time}</div>
        <div>
          <div class="timeline-title">${transitWindow.title}</div>
          <div class="timeline-meta">${transitWindow.note}</div>
        </div>
        <div class="tag-row">
          <span class="tag">Score ${transitWindow.score}</span>
          ${tags || '<span class="tag muted-tag">No close contacts</span>'}
        </div>
      </article>
    `;
  }).join("");
}

function renderSummary(windows, preset) {
  const topWindow = windows.reduce((best, current) => {
    return current.score > best.score ? current : best;
  }, windows[0]);
  const allDetected = windows.flatMap((transitWindow) => transitWindow.detectedAspects);
  const uniqueTracked = new Set(allDetected.map((aspect) => aspect.aspectId));

  const benefic = allDetected.filter((aspect) => aspect.tone === "support").length;
  const stress = allDetected.filter((aspect) => aspect.tone === "stress").length;

  bestScore.textContent = topWindow ? topWindow.score : "--";
  beneficCount.textContent = benefic;
  stressCount.textContent = stress;
  trackedCount.textContent = uniqueTracked.size;
  angularCount.textContent = topWindow
    ? window.ElectionalPresets.filterPositionsForPreset(topWindow.positions, preset).filter((planet) => planet.isAngular).length
    : "--";
  presetLabel.textContent = preset.shortName;
  orbLabel.textContent = window.ElectionalPresets.summarizeOrb(preset);
}

function renderPositions(snapshot, state) {
  positionTimestamp.textContent = `${window.ElectionalTimezone.formatInTimezone(snapshot.date, state.timezone)} / ${window.ElectionalEphemeris.engine}`;

  positionGrid.innerHTML = snapshot.positions.map((planet) => `
    <article class="position-row ${planet.isPresetPoint ? "" : "muted-position"}">
      <div>
        <strong>${planet.name}</strong>
        <small>House ${planet.house}${planet.isAngular ? ` / ${planet.closestAngle.shortName}` : ""}${planet.dignity ? ` / ${planet.dignity.label}` : ""}</small>
      </div>
      <span>${window.ElectionalEphemeris.formatPosition(planet)}</span>
    </article>
  `).join("");
}

function renderAngles(snapshot) {
  angleGrid.innerHTML = snapshot.angles.map((angle) => `
    <article class="angle-card">
      <span>${angle.name}</span>
      <strong>${window.ElectionalHouses.formatAngle(angle)}</strong>
    </article>
  `).join("");
}

function renderDetectedAspects(snapshot) {
  if (!snapshot.detectedAspects.length) {
    detectedGrid.innerHTML = `
      <article class="empty-state">
        <strong>No selected aspects in orb</strong>
        <span>Try enabling more aspect types or changing the time.</span>
      </article>
    `;
    return;
  }

  detectedGrid.innerHTML = snapshot.detectedAspects.map((aspect) => {
    const tone = aspect.tone === "stress" ? " stress" : "";
    return `
      <article class="detected-card${tone}">
        <strong>${aspect.label}</strong>
        <span>${aspect.orbText} orb / ${aspect.exactAngle} deg exact / limit ${aspect.orbLimit} deg</span>
      </article>
    `;
  }).join("");
}

function renderValidation() {
  const report = window.ElectionalValidation.runJplValidation();
  const angleReport = window.ElectionalValidation.runAngleSanityValidation();
  const swissAngleReport = window.ElectionalValidation.runSwissAngleValidation();
  const worstBodies = [...report.bodies]
    .sort((first, second) => Math.abs(second.longitudeDelta) - Math.abs(first.longitudeDelta))
    .slice(0, 3);

  validationSource.textContent = `${report.source} / tolerance ${report.tolerance} deg`;
  validationPanel.innerHTML = `
    <article class="validation-summary ${report.pass ? "pass" : "fail"}">
      <span>${report.label}</span>
      <strong>${report.pass ? "Pass" : "Review"}</strong>
      <small>Max longitude delta: ${report.maxLongitudeDelta.toFixed(4)} deg</small>
    </article>
    <article class="validation-summary ${angleReport.pass ? "pass" : "fail"}">
      <span>${angleReport.label}</span>
      <strong>${angleReport.pass ? "Pass" : "Review"}</strong>
      <small>ASC ${window.ElectionalEphemeris.formatZodiacPosition(angleReport.ascendant.zodiac)} / MC ${window.ElectionalEphemeris.formatZodiacPosition(angleReport.midheaven.zodiac)}</small>
    </article>
    <article class="validation-summary ${swissAngleReport.pass ? "pass" : "fail"}">
      <span>${swissAngleReport.label}</span>
      <strong>${swissAngleReport.pass ? "Pass" : "Review"}</strong>
      <small>ASC delta ${swissAngleReport.ascendantDelta.toFixed(4)} deg / MC delta ${swissAngleReport.midheavenDelta.toFixed(4)} deg</small>
    </article>
    ${worstBodies.map((body) => `
      <article class="validation-row">
        <strong>${body.name}</strong>
        <span>${body.longitudeDelta >= 0 ? "+" : ""}${body.longitudeDelta.toFixed(4)} deg</span>
      </article>
    `).join("")}
  `;

  return report.pass && angleReport.pass && swissAngleReport.pass;
}

function render() {
  const state = getFormState();
  const windows = window.ElectionalTransits.buildTransitWindows(state);
  const snapshot = window.ElectionalTransits.buildElectionSnapshot(state);
  const preset = snapshot.preset;
  const objectiveLabel = form.elements.objective.selectedOptions[0].textContent;

  chartTitle.textContent = "Natal Chart";
  chartMeta.innerHTML = `
    <span>${state.date} ${state.time}</span>
    <span>${state.location}</span>
    <span>${state.latitude.toFixed(4)}, ${state.longitude.toFixed(4)}</span>
    <span>${state.timezone}</span>
  `;
  workspaceTitle.textContent = `${objectiveLabel} windows near ${state.location}`;
  timezoneLabel.textContent = state.timezone.replaceAll("_", " ");
  renderSummary(windows, preset);
  renderChartWheel(snapshot);
  renderTimeline(windows);
  renderPositions(snapshot, state);
  renderAngles(snapshot);
  renderDetectedAspects(snapshot);
  const validationPasses = renderValidation();
  statusLocation.textContent = state.location;
  statusTime.textContent = window.ElectionalTimezone.formatInTimezone(snapshot.date, state.timezone);
  statusPreset.textContent = preset.name;
  statusValidation.textContent = validationPasses ? "Pass" : "Review";
}

locationPresetInput.addEventListener("change", () => {
  applyLocationPreset();
  render();
});

form.addEventListener("input", render);
presetInput.addEventListener("change", () => {
  applyPresetSelection();
  render();
});
applyPresetSelection();
render();
