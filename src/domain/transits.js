const OBJECTIVE_WEIGHTS = {
  launch: ["trine", "conjunction", "sextile"],
  meeting: ["sextile", "trine", "conjunction"],
  creative: ["trine", "sextile", "conjunction"],
  relationship: ["trine", "sextile", "opposition"],
};

const WINDOW_TEMPLATES = [
  {
    offsetHours: 0,
    title: "Opening election",
    note: "Use this as the first candidate moment for a focused chart review.",
    aspects: ["conjunction", "trine"],
  },
  {
    offsetHours: 3,
    title: "Midday refinement",
    note: "A practical checkpoint for balancing supportive and stressful contacts.",
    aspects: ["trine", "square"],
  },
  {
    offsetHours: 6,
    title: "Late-day alternative",
    note: "Good for comparing whether the Moon and angles improve later.",
    aspects: ["sextile", "opposition"],
  },
];

function buildTransitWindows({ date, time, objective, aspects }) {
  const selectedAspects = aspects.length ? aspects : ["conjunction", "trine", "square"];
  const preferred = OBJECTIVE_WEIGHTS[objective] ?? OBJECTIVE_WEIGHTS.launch;
  const baseDate = new Date(`${date}T${time || "09:00"}`);

  return WINDOW_TEMPLATES.map((template, index) => {
    const windowDate = new Date(baseDate);
    windowDate.setHours(baseDate.getHours() + template.offsetHours);

    const activeAspects = template.aspects.filter((aspect) => selectedAspects.includes(aspect));
    const preferredMatches = activeAspects.filter((aspect) => preferred.includes(aspect)).length;
    const stressPenalty = activeAspects.filter((aspect) => aspect === "square" || aspect === "opposition").length;

    return {
      ...template,
      aspects: activeAspects,
      time: windowDate.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }),
      score: Math.max(42, 74 + preferredMatches * 9 - stressPenalty * 7 - index * 3),
    };
  });
}

window.ElectionalTransits = {
  buildTransitWindows,
};
