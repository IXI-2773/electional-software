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

window.ElectionalAspects = {
  ASPECTS,
  getAspectById,
};
