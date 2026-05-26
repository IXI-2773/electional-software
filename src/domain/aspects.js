const ASPECTS = [
  {
    id: "conjunction",
    name: "Conjunction",
    angle: 0,
    defaultOrb: 8,
    tone: "mixed",
    meaning: "Merges planetary significations and intensifies the elected moment.",
  },
  {
    id: "trine",
    name: "Trine",
    angle: 120,
    defaultOrb: 7,
    tone: "support",
    meaning: "Shows ease, flow, and cooperation between the planets involved.",
  },
  {
    id: "square",
    name: "Square",
    angle: 90,
    defaultOrb: 6,
    tone: "stress",
    meaning: "Signals friction, urgency, and pressure that may require management.",
  },
  {
    id: "opposition",
    name: "Opposition",
    angle: 180,
    defaultOrb: 7,
    tone: "stress",
    meaning: "Highlights polarization, exposure, and competing priorities.",
  },
  {
    id: "sextile",
    name: "Sextile",
    angle: 60,
    defaultOrb: 5,
    tone: "support",
    meaning: "Offers opportunity through intentional action and coordination.",
  },
];

function getAspectById(id) {
  return ASPECTS.find((aspect) => aspect.id === id);
}

function getAngularDistance(firstLongitude, secondLongitude) {
  const rawDistance = Math.abs(firstLongitude - secondLongitude) % 360;
  return rawDistance > 180 ? 360 - rawDistance : rawDistance;
}

function formatOrb(orb) {
  const degrees = Math.floor(orb);
  const minutes = Math.round((orb - degrees) * 60);
  return `${degrees} deg ${String(minutes).padStart(2, "0")} min`;
}

function detectAspects(positions, selectedAspectIds) {
  const selected = ASPECTS.filter((aspect) => selectedAspectIds.includes(aspect.id));
  const detected = [];

  for (let firstIndex = 0; firstIndex < positions.length; firstIndex += 1) {
    for (let secondIndex = firstIndex + 1; secondIndex < positions.length; secondIndex += 1) {
      const first = positions[firstIndex];
      const second = positions[secondIndex];
      const distance = getAngularDistance(first.longitude, second.longitude);

      selected.forEach((aspect) => {
        const orb = Math.abs(distance - aspect.angle);
        if (orb <= aspect.defaultOrb) {
          detected.push({
            aspectId: aspect.id,
            aspectName: aspect.name,
            exactAngle: aspect.angle,
            tone: aspect.tone,
            orb,
            orbText: formatOrb(orb),
            bodies: [first.name, second.name],
            label: `${first.name} ${aspect.name.toLowerCase()} ${second.name}`,
          });
        }
      });
    }
  }

  return detected.sort((first, second) => first.orb - second.orb);
}

window.ElectionalAspects = {
  ASPECTS,
  detectAspects,
  getAngularDistance,
  getAspectById,
};
