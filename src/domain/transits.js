const OBJECTIVE_WEIGHTS = {
  launch: ["trine", "conjunction", "sextile"],
  meeting: ["sextile", "trine", "conjunction"],
  creative: ["trine", "sextile", "conjunction"],
  relationship: ["trine", "sextile", "opposition"],
};

const WINDOW_OFFSETS = [0, 2, 4, 6, 8, 10];

function buildDate(date, time) {
  return new Date(`${date}T${time || "09:00"}`);
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

function scoreWindow(detectedAspects, preferredAspects) {
  const counts = getToneCounts(detectedAspects);
  const objectiveMatches = detectedAspects.filter((aspect) => preferredAspects.includes(aspect.aspectId)).length;
  const closeContacts = detectedAspects.filter((aspect) => aspect.orb <= 2).length;
  const rawScore = 58 + counts.support * 8 + counts.mixed * 3 + objectiveMatches * 5 + closeContacts * 4 - counts.stress * 9;

  return Math.max(10, Math.min(99, rawScore));
}

function describeWindow(detectedAspects) {
  if (!detectedAspects.length) {
    return "Quiet window with no selected major aspects in orb.";
  }

  const strongest = detectedAspects[0];
  return `Strongest contact: ${strongest.label} with ${strongest.orbText} orb.`;
}

function buildElectionSnapshot({ date, time, aspects }) {
  const selectedAspects = aspects.length ? aspects : ["conjunction", "trine", "square"];
  const chartDate = buildDate(date, time);
  const positions = window.ElectionalEphemeris.getPlanetPositions(chartDate);
  const detectedAspects = window.ElectionalAspects.detectAspects(positions, selectedAspects);

  return {
    date: chartDate,
    positions,
    detectedAspects,
  };
}

function buildTransitWindows({ date, time, objective, aspects }) {
  const selectedAspects = aspects.length ? aspects : ["conjunction", "trine", "square"];
  const preferred = OBJECTIVE_WEIGHTS[objective] ?? OBJECTIVE_WEIGHTS.launch;
  const baseDate = buildDate(date, time);

  return WINDOW_OFFSETS.map((offsetHours) => {
    const windowDate = new Date(baseDate);
    windowDate.setHours(baseDate.getHours() + offsetHours);
    const positions = window.ElectionalEphemeris.getPlanetPositions(windowDate);
    const detectedAspects = window.ElectionalAspects.detectAspects(positions, selectedAspects);
    const score = scoreWindow(detectedAspects, preferred);

    const title = score >= 76
      ? "High-priority election"
      : score >= 60
        ? "Workable election"
        : "Use with caution";

    return {
      detectedAspects,
      note: describeWindow(detectedAspects),
      score,
      time: windowDate.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }),
      title,
    };
  }).sort((first, second) => second.score - first.score);
}

window.ElectionalTransits = {
  buildElectionSnapshot,
  buildTransitWindows,
};
