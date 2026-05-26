const form = document.querySelector("#electionForm");
const dateInput = document.querySelector("#dateInput");
const timeline = document.querySelector("#timeline");
const aspectGrid = document.querySelector("#aspectGrid");
const bestScore = document.querySelector("#bestScore");
const beneficCount = document.querySelector("#beneficCount");
const stressCount = document.querySelector("#stressCount");
const trackedCount = document.querySelector("#trackedCount");
const workspaceTitle = document.querySelector("#workspaceTitle");

dateInput.value = new Date().toISOString().slice(0, 10);

function getFormState() {
  const data = new FormData(form);
  return {
    date: data.get("date"),
    time: data.get("time"),
    location: data.get("location"),
    objective: data.get("objective"),
    aspects: data.getAll("aspect"),
  };
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
    const tags = transitWindow.aspects
      .map((id) => window.ElectionalAspects.getAspectById(id))
      .filter(Boolean)
      .map((aspect) => {
        const tone = aspect.tone === "stress" ? " stress" : "";
        return `<span class="tag${tone}">${aspect.name}</span>`;
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
          ${tags}
        </div>
      </article>
    `;
  }).join("");
}

function renderSummary(windows, selectedAspects) {
  const topWindow = windows.reduce((best, current) => {
    return current.score > best.score ? current : best;
  }, windows[0]);

  const selectedDefinitions = selectedAspects.map(window.ElectionalAspects.getAspectById).filter(Boolean);
  const benefic = selectedDefinitions.filter((aspect) => aspect.tone === "support").length;
  const stress = selectedDefinitions.filter((aspect) => aspect.tone === "stress").length;

  bestScore.textContent = topWindow ? topWindow.score : "--";
  beneficCount.textContent = benefic;
  stressCount.textContent = stress;
  trackedCount.textContent = selectedAspects.length;
}

function render() {
  const state = getFormState();
  const windows = window.ElectionalTransits.buildTransitWindows(state);
  const objectiveLabel = form.elements.objective.selectedOptions[0].textContent;

  workspaceTitle.textContent = `${objectiveLabel} windows near ${state.location}`;
  renderSummary(windows, state.aspects);
  renderTimeline(windows);
  renderAspectLibrary(state.aspects);
}

form.addEventListener("input", render);
render();
