const CLASSICAL_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"];
const ALL_MAJOR_PLANETS = [...CLASSICAL_PLANETS, "Uranus", "Neptune", "Pluto"];

const ELECTIONAL_PRESETS = [
  {
    id: "transit-1-degree",
    name: "Transit 1 Degree",
    shortName: "Transit 1 deg",
    source: "Capricorn Prometheus: transits_1_deg",
    description: "Strict transit search mode for exact election windows. Every selected major aspect uses a 1 degree orb.",
    aspectIds: ["conjunction", "trine", "sextile", "square", "opposition"],
    aspectOrbs: {
      conjunction: 1,
      trine: 1,
      sextile: 1,
      square: 1,
      opposition: 1,
    },
    pointNames: ALL_MAJOR_PLANETS,
    preferredAspects: ["trine", "sextile", "conjunction"],
    scoring: {
      supportWeight: 13,
      mixedWeight: 4,
      stressPenalty: 12,
      preferredWeight: 7,
      closeContactOrb: 0.35,
      closeContactWeight: 9,
      angularMultiplier: 1.1,
      dignityWeight: 0,
    },
  },
  {
    id: "traditional-lilly",
    name: "Traditional Lilly",
    shortName: "Lilly",
    source: "Capricorn Prometheus: Traditional - Lilly",
    description: "Classical seven-planet election mode with essential dignity scoring and Lilly-inspired rulership emphasis.",
    aspectIds: ["conjunction", "sextile", "square", "trine", "opposition"],
    aspectOrbs: {
      conjunction: 6,
      sextile: 4,
      square: 5,
      trine: 5,
      opposition: 6,
    },
    pointNames: CLASSICAL_PLANETS,
    preferredAspects: ["trine", "sextile"],
    scoring: {
      supportWeight: 9,
      mixedWeight: 3,
      stressPenalty: 9,
      preferredWeight: 6,
      closeContactOrb: 1.5,
      closeContactWeight: 5,
      angularMultiplier: 1.35,
      dignityWeight: 2,
    },
  },
  {
    id: "medieval-electional",
    name: "Medieval Electional",
    shortName: "Medieval",
    source: "Capricorn Prometheus: Medieval / Bonatti-Ptolemy references",
    description: "Stricter classical electional mode that rewards dignified benefics and penalizes hard malefic contact.",
    aspectIds: ["conjunction", "trine", "sextile", "square", "opposition"],
    aspectOrbs: {
      conjunction: 4,
      trine: 4,
      sextile: 3,
      square: 3,
      opposition: 4,
    },
    pointNames: CLASSICAL_PLANETS,
    preferredAspects: ["trine", "sextile"],
    scoring: {
      supportWeight: 11,
      mixedWeight: 2,
      stressPenalty: 14,
      preferredWeight: 7,
      closeContactOrb: 1,
      closeContactWeight: 6,
      angularMultiplier: 1.5,
      dignityWeight: 3,
    },
  },
];

const RULERS = {
  Aries: "Mars",
  Taurus: "Venus",
  Gemini: "Mercury",
  Cancer: "Moon",
  Leo: "Sun",
  Virgo: "Mercury",
  Libra: "Venus",
  Scorpio: "Mars",
  Sagittarius: "Jupiter",
  Capricorn: "Saturn",
  Aquarius: "Saturn",
  Pisces: "Jupiter",
};

const EXALTATIONS = {
  Aries: "Sun",
  Taurus: "Moon",
  Cancer: "Jupiter",
  Virgo: "Mercury",
  Libra: "Saturn",
  Capricorn: "Mars",
  Pisces: "Venus",
};

const DETRIMENTS = {
  Aries: "Venus",
  Taurus: "Mars",
  Gemini: "Jupiter",
  Cancer: "Saturn",
  Leo: "Saturn",
  Virgo: "Jupiter",
  Libra: "Mars",
  Scorpio: "Venus",
  Sagittarius: "Mercury",
  Capricorn: "Moon",
  Aquarius: "Sun",
  Pisces: "Mercury",
};

const FALLS = {
  Aries: "Saturn",
  Cancer: "Mars",
  Virgo: "Venus",
  Libra: "Sun",
  Scorpio: "Moon",
  Capricorn: "Jupiter",
  Pisces: "Mercury",
};

function getPreset(id) {
  return ELECTIONAL_PRESETS.find((preset) => preset.id === id) ?? ELECTIONAL_PRESETS[0];
}

function usesPoint(preset, planetName) {
  return preset.pointNames.includes(planetName);
}

function filterPositionsForPreset(positions, preset) {
  return positions.filter((planet) => usesPoint(preset, planet.name));
}

function getEssentialDignity(planet) {
  const sign = planet.zodiac.sign;

  if (RULERS[sign] === planet.name) {
    return { label: "Domicile", score: 5 };
  }

  if (EXALTATIONS[sign] === planet.name) {
    return { label: "Exalted", score: 4 };
  }

  if (DETRIMENTS[sign] === planet.name) {
    return { label: "Detriment", score: -5 };
  }

  if (FALLS[sign] === planet.name) {
    return { label: "Fall", score: -4 };
  }

  if (!CLASSICAL_PLANETS.includes(planet.name)) {
    return { label: "Outer", score: 0 };
  }

  return { label: "Peregrine", score: 0 };
}

function applyDignities(positions, preset) {
  return positions.map((planet) => ({
    ...planet,
    isPresetPoint: usesPoint(preset, planet.name),
    dignity: getEssentialDignity(planet),
  }));
}

function getDignityScore(positions, preset) {
  return filterPositionsForPreset(positions, preset).reduce((total, planet) => total + planet.dignity.score, 0);
}

function summarizeOrb(preset) {
  const values = Object.values(preset.aspectOrbs);
  const unique = [...new Set(values)].sort((first, second) => first - second);

  if (unique.length === 1) {
    return `${unique[0]} deg`;
  }

  return `${unique[0]}-${unique[unique.length - 1]} deg`;
}

window.ElectionalPresets = {
  ELECTIONAL_PRESETS,
  applyDignities,
  filterPositionsForPreset,
  getDignityScore,
  getEssentialDignity,
  getPreset,
  summarizeOrb,
};
