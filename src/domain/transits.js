const OBJECTIVE_WEIGHTS = {
  launch: ["trine", "conjunction", "sextile"],
  meeting: ["sextile", "trine", "conjunction"],
  creative: ["trine", "sextile", "conjunction"],
  relationship: ["trine", "sextile", "opposition"],
};

const WINDOW_OFFSETS = [0, 2, 4, 6, 8, 10];

function buildDate(date, time, timezone) {
  return window.ElectionalTimezone.zonedTimeToUtc(date, time, timezone || "UTC");
}

function getToneCounts(detectedAspects) {
  return detectedAspects.reduce((counts, aspect) => {
    if (aspect.tone === "support") {
      counts.support += 1;
    }

    if (aspect.tone === "stress") {
      counts.stress += 1;
    }

    if (aspect.tone === "mixed") {
      counts.mixed += 1;
    }

    return counts;
  }, { support: 0, stress: 0, mixed: 0 });
}

function scoreWindow(detectedAspects, preferredAspects, positions, preset) {
  const counts = getToneCounts(detectedAspects);
  const scoring = preset.scoring;
  const objectiveMatches = detectedAspects.filter((aspect) => preferredAspects.includes(aspect.aspectId)).length;
  const closeContacts = detectedAspects.filter((aspect) => aspect.orb <= scoring.closeContactOrb).length;
  const scoringPositions = window.ElectionalPresets.filterPositionsForPreset(positions, preset);
  const angularityScore = window.ElectionalHouses.getAngularityScore(scoringPositions) * scoring.angularMultiplier;
  const dignityScore = window.ElectionalPresets.getDignityScore(positions, preset) * scoring.dignityWeight;
  const rawScore = 58
    + counts.support * scoring.supportWeight
    + counts.mixed * scoring.mixedWeight
    + objectiveMatches * scoring.preferredWeight
    + closeContacts * scoring.closeContactWeight
    + angularityScore
    + dignityScore
    - counts.stress * scoring.stressPenalty;

  return Math.round(Math.max(10, Math.min(99, rawScore)));
}

function describeWindow(detectedAspects, positions, preset) {
  const scoringPositions = preset
    ? window.ElectionalPresets.filterPositionsForPreset(positions, preset)
    : positions;
  const angularBodies = scoringPositions
    .filter((planet) => planet.isAngular)
    .map((planet) => `${planet.name} near ${planet.closestAngle.shortName}`);

  if (angularBodies.length) {
    return `Angular emphasis: ${angularBodies.slice(0, 2).join(", ")}.`;
  }

  if (!detectedAspects.length) {
    return "Quiet window with no selected major aspects in orb.";
  }

  const strongest = detectedAspects[0];
  return `Strongest contact: ${strongest.label} with ${strongest.orbText} orb.`;
}

function buildElectionSnapshot({ date, time, timezone, latitude, longitude, aspects, presetId }) {
  const preset = window.ElectionalPresets.getPreset(presetId);
  const selectedAspects = aspects.length ? aspects : preset.aspectIds;
  const chartDate = buildDate(date, time, timezone);
  const angles = window.ElectionalHouses.calculateAngles({ date: chartDate, latitude, longitude });
  const positions = window.ElectionalPresets.applyDignities(
    window.ElectionalHouses.enrichPositionsWithHouses(
      window.ElectionalEphemeris.getPlanetPositions(chartDate),
      angles,
    ),
    preset,
  );
  const detectedAspects = window.ElectionalAspects.detectAspects(
    window.ElectionalPresets.filterPositionsForPreset(positions, preset),
    selectedAspects,
    { aspectOrbs: preset.aspectOrbs },
  );

  return {
    angles,
    date: chartDate,
    preset,
    positions,
    detectedAspects,
  };
}

function buildTransitWindows({ date, time, timezone, latitude, longitude, objective, aspects, presetId }) {
  const preset = window.ElectionalPresets.getPreset(presetId);
  const selectedAspects = aspects.length ? aspects : preset.aspectIds;
  const preferred = preset.preferredAspects.length
    ? preset.preferredAspects
    : OBJECTIVE_WEIGHTS[objective] ?? OBJECTIVE_WEIGHTS.launch;
  const baseDate = buildDate(date, time, timezone);

  return WINDOW_OFFSETS.map((offsetHours) => {
    const windowDate = new Date(baseDate);
    windowDate.setHours(baseDate.getHours() + offsetHours);
    const angles = window.ElectionalHouses.calculateAngles({ date: windowDate, latitude, longitude });
    const positions = window.ElectionalPresets.applyDignities(
      window.ElectionalHouses.enrichPositionsWithHouses(
        window.ElectionalEphemeris.getPlanetPositions(windowDate),
        angles,
      ),
      preset,
    );
    const detectedAspects = window.ElectionalAspects.detectAspects(
      window.ElectionalPresets.filterPositionsForPreset(positions, preset),
      selectedAspects,
      { aspectOrbs: preset.aspectOrbs },
    );
    const score = scoreWindow(detectedAspects, preferred, positions, preset);

    const title = score >= 76
      ? "High-priority election"
      : score >= 60
        ? "Workable election"
        : "Use with caution";

    return {
      detectedAspects,
      angles,
      note: describeWindow(detectedAspects, positions, preset),
      preset,
      positions,
      score,
      time: new Intl.DateTimeFormat("en-US", {
        timeZone: timezone || "UTC",
        hour: "numeric",
        minute: "2-digit",
      }).format(windowDate),
      title,
    };
  }).sort((first, second) => second.score - first.score);
}

window.ElectionalTransits = {
  buildElectionSnapshot,
  buildTransitWindows,
};
