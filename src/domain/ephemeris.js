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
  { id: "sun", name: "Sun", astronomyBody: "Sun" },
  { id: "moon", name: "Moon", astronomyBody: "Moon" },
  { id: "mercury", name: "Mercury", astronomyBody: "Mercury" },
  { id: "venus", name: "Venus", astronomyBody: "Venus" },
  { id: "mars", name: "Mars", astronomyBody: "Mars" },
  { id: "jupiter", name: "Jupiter", astronomyBody: "Jupiter" },
  { id: "saturn", name: "Saturn", astronomyBody: "Saturn" },
  { id: "uranus", name: "Uranus", astronomyBody: "Uranus" },
  { id: "neptune", name: "Neptune", astronomyBody: "Neptune" },
  { id: "pluto", name: "Pluto", astronomyBody: "Pluto" },
];

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

function getEclipticCoordinates(bodyName, date) {
  if (!window.Astronomy) {
    throw new Error("Astronomy Engine is not loaded.");
  }

  const body = window.Astronomy.Body[bodyName];

  if (bodyName === "Sun") {
    const sun = window.Astronomy.SunPosition(date);
    return {
      latitude: sun.elat,
      longitude: sun.elon,
      distanceAu: sun.vec ? sun.vec.Length() : null,
    };
  }

  const vector = window.Astronomy.GeoVector(body, date, true);
  const ecliptic = window.Astronomy.Ecliptic(vector);

  return {
    latitude: ecliptic.elat,
    longitude: ecliptic.elon,
    distanceAu: ecliptic.vec ? ecliptic.vec.Length() : null,
  };
}

function getPlanetPositions(date) {
  return PLANET_MODELS.map((planet) => {
    const coordinates = getEclipticCoordinates(planet.astronomyBody, date);
    const longitude = normalizeDegrees(coordinates.longitude);

    return {
      ...planet,
      latitude: coordinates.latitude,
      longitude,
      distanceAu: coordinates.distanceAu,
      zodiac: getZodiacPosition(longitude),
    };
  });
}

function formatPosition(planet) {
  const minute = String(planet.zodiac.minute).padStart(2, "0");
  return `${planet.zodiac.degree} ${planet.zodiac.sign} ${minute}`;
}

window.ElectionalEphemeris = {
  engine: "Astronomy Engine",
  PLANET_MODELS,
  ZODIAC_SIGNS,
  formatPosition,
  getPlanetPositions,
  getZodiacPosition,
  normalizeDegrees,
};
