const ZODIAC_SIGNS = [
  "Aries",
  "Taurus",
  "Gemini",
  "Cancer",
  "Leo",
  "Virgo",
  "Libra",
  "Scorpio",
  "Sagittarius",
  "Capricorn",
  "Aquarius",
  "Pisces",
];

const PLANET_MODELS = [
  { id: "sun", name: "Sun", j2000Longitude: 280.46, dailyMotion: 0.98564736 },
  { id: "moon", name: "Moon", j2000Longitude: 218.32, dailyMotion: 13.176396 },
  { id: "mercury", name: "Mercury", j2000Longitude: 252.25, dailyMotion: 4.09233445 },
  { id: "venus", name: "Venus", j2000Longitude: 181.98, dailyMotion: 1.60213034 },
  { id: "mars", name: "Mars", j2000Longitude: 355.43, dailyMotion: 0.52402068 },
  { id: "jupiter", name: "Jupiter", j2000Longitude: 34.35, dailyMotion: 0.08308529 },
  { id: "saturn", name: "Saturn", j2000Longitude: 50.08, dailyMotion: 0.03344414 },
];

const J2000 = Date.UTC(2000, 0, 1, 12, 0, 0);
const DAY_MS = 24 * 60 * 60 * 1000;

function normalizeDegrees(value) {
  return ((value % 360) + 360) % 360;
}

function getZodiacPosition(longitude) {
  const normalized = normalizeDegrees(longitude);
  const signIndex = Math.floor(normalized / 30);
  const signDegree = normalized % 30;
  return {
    sign: ZODIAC_SIGNS[signIndex],
    degree: Math.floor(signDegree),
    minute: Math.round((signDegree % 1) * 60),
  };
}

function getPlanetPositions(date) {
  const daysSinceJ2000 = (date.getTime() - J2000) / DAY_MS;

  return PLANET_MODELS.map((planet) => {
    const longitude = normalizeDegrees(planet.j2000Longitude + planet.dailyMotion * daysSinceJ2000);
    const zodiac = getZodiacPosition(longitude);

    return {
      ...planet,
      longitude,
      zodiac,
    };
  });
}

function formatPosition(planet) {
  const minute = String(planet.zodiac.minute).padStart(2, "0");
  return `${planet.zodiac.degree} ${planet.zodiac.sign} ${minute}`;
}

window.ElectionalEphemeris = {
  PLANET_MODELS,
  ZODIAC_SIGNS,
  formatPosition,
  getPlanetPositions,
  getZodiacPosition,
  normalizeDegrees,
};
