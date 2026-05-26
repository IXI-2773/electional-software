const form = document.querySelector("#electionForm");
const dateInput = document.querySelector("#dateInput");
const locationPresetInput = document.querySelector("#locationPresetInput");
const locationInput = document.querySelector("#locationInput");
const latitudeInput = document.querySelector("#latitudeInput");
const longitudeInput = document.querySelector("#longitudeInput");
const timezoneInput = document.querySelector("#timezoneInput");
const timeline = document.querySelector("#timeline");
const aspectGrid = document.querySelector("#aspectGrid");
const bestScore = document.querySelector("#bestScore");
const beneficCount = document.querySelector("#beneficCount");
const stressCount = document.querySelector("#stressCount");
const trackedCount = document.querySelector("#trackedCount");
const timezoneLabel = document.querySelector("#timezoneLabel");
const workspaceTitle = document.querySelector("#workspaceTitle");
const positionTimestamp = document.querySelector("#positionTimestamp");
const positionGrid = document.querySelector("#positionGrid");
const detectedGrid = document.querySelector("#detectedGrid");

dateInput.value = new Date().toISOString().slice(0, 10);

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
    aspects: data.getAll("aspect"),
  };
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

function renderAspectLibrary(selectedAspects) {
  aspectGrid.innerHTML = window.ElectionalAspects.ASPECTS.map((aspect) => {
    const isSelected = selectedAspects.includes(aspect.id);
    return `
      <article class="aspect-card">
        <span>${aspect.angle} degrees / ${aspect.defaultOrb} degree orb</span>
        <strong>${aspect.name}${isSelected ? " - tracked" : ""}</strong>
        <p>${aspect.meaning}</p>
      </article>
    `;
  }).join("");
}

function renderTimeline(windows) {
  timeline.innerHTML = windows.map((transitWindow) => {
    const tags = transitWindow.detectedAspects
      .slice(0, 4)
      .map((aspect) => {
        const tone = aspect.tone === "stress" ? " stress" : "";
        return `<span class="tag${tone}">${aspect.label}</span>`;
      })
      .join("");

    return `
      <article class="timeline-card">
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

function renderSummary(windows) {
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
}

function renderPositions(snapshot, state) {
  positionTimestamp.textContent = `${window.ElectionalTimezone.formatInTimezone(snapshot.date, state.timezone)} / ${window.ElectionalEphemeris.engine}`;

  positionGrid.innerHTML = snapshot.positions.map((planet) => `
    <article class="position-row">
      <strong>${planet.name}</strong>
      <span>${window.ElectionalEphemeris.formatPosition(planet)}</span>
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
        <span>${aspect.orbText} orb / ${aspect.exactAngle} deg exact</span>
      </article>
    `;
  }).join("");
}

function render() {
  const state = getFormState();
  const windows = window.ElectionalTransits.buildTransitWindows(state);
  const snapshot = window.ElectionalTransits.buildElectionSnapshot(state);
  const objectiveLabel = form.elements.objective.selectedOptions[0].textContent;

  workspaceTitle.textContent = `${objectiveLabel} windows near ${state.location}`;
  timezoneLabel.textContent = state.timezone.replaceAll("_", " ");
  renderSummary(windows);
  renderTimeline(windows);
  renderPositions(snapshot, state);
  renderDetectedAspects(snapshot);
  renderAspectLibrary(state.aspects);
}

locationPresetInput.addEventListener("change", () => {
  applyLocationPreset();
  render();
});

form.addEventListener("input", render);
render();
