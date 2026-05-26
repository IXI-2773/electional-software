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

function scoreWindow(detectedAspects, preferredAspects, positions) {
  const counts = getToneCounts(detectedAspects);
  const objectiveMatches = detectedAspects.filter((aspect) => preferredAspects.includes(aspect.aspectId)).length;
  const closeContacts = detectedAspects.filter((aspect) => aspect.orb <= 2).length;
  const angularityScore = window.ElectionalHouses.getAngularityScore(positions);
  const rawScore = 58 + counts.support * 8 + counts.mixed * 3 + objectiveMatches * 5 + closeContacts * 4 + angularityScore - counts.stress * 9;

  return Math.max(10, Math.min(99, rawScore));
}

function describeWindow(detectedAspects, positions) {
  const angularBodies = positions
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

function buildElectionSnapshot({ date, time, timezone, latitude, longitude, aspects }) {
  const selectedAspects = aspects.length ? aspects : ["conjunction", "trine", "square"];
  const chartDate = buildDate(date, time, timezone);
  const angles = window.ElectionalHouses.calculateAngles({ date: chartDate, latitude, longitude });
  const positions = window.ElectionalHouses.enrichPositionsWithHouses(
    window.ElectionalEphemeris.getPlanetPositions(chartDate),
    angles,
  );
  const detectedAspects = window.ElectionalAspects.detectAspects(positions, selectedAspects);

  return {
    angles,
    date: chartDate,
    positions,
    detectedAspects,
  };
}

function buildTransitWindows({ date, time, timezone, latitude, longitude, objective, aspects }) {
  const selectedAspects = aspects.length ? aspects : ["conjunction", "trine", "square"];
  const preferred = OBJECTIVE_WEIGHTS[objective] ?? OBJECTIVE_WEIGHTS.launch;
  const baseDate = buildDate(date, time, timezone);

  return WINDOW_OFFSETS.map((offsetHours) => {
    const windowDate = new Date(baseDate);
    windowDate.setHours(baseDate.getHours() + offsetHours);
    const angles = window.ElectionalHouses.calculateAngles({ date: windowDate, latitude, longitude });
    const positions = window.ElectionalHouses.enrichPositionsWithHouses(
      window.ElectionalEphemeris.getPlanetPositions(windowDate),
      angles,
    );
    const detectedAspects = window.ElectionalAspects.detectAspects(positions, selectedAspects);
    const score = scoreWindow(detectedAspects, preferred, positions);

    const title = score >= 76
      ? "High-priority election"
      : score >= 60
        ? "Workable election"
        : "Use with caution";

    return {
      detectedAspects,
      angles,
      note: describeWindow(detectedAspects, positions),
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
