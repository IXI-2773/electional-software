const ANGLE_DEFINITIONS = [
  { id: "asc", name: "Ascendant", shortName: "ASC" },
  { id: "mc", name: "Midheaven", shortName: "MC" },
  { id: "dsc", name: "Descendant", shortName: "DSC" },
  { id: "ic", name: "Imum Coeli", shortName: "IC" },
];

const BENEFIC_BODIES = new Set(["Venus", "Jupiter"]);
const CHALLENGING_BODIES = new Set(["Mars", "Saturn"]);
const ANGULAR_ORB = 8;

function degreesToRadians(degrees) {
  return degrees * Math.PI / 180;
}

function radiansToDegrees(radians) {
  return radians * 180 / Math.PI;
}

function getAngleDistance(firstLongitude, secondLongitude) {
  const distance = window.ElectionalEphemeris.normalizeDegrees(firstLongitude - secondLongitude);
  return distance > 180 ? 360 - distance : distance;
}

function getLocalSiderealDegrees(date, longitude) {
  const siderealHours = window.Astronomy.SiderealTime(date);
  return window.ElectionalEphemeris.normalizeDegrees(siderealHours * 15 + longitude);
}

function getObliquity(date) {
  return window.Astronomy.e_tilt(date).tobl;
}

function calculateMidheaven(localSiderealDegrees, obliquityDegrees) {
  const theta = degreesToRadians(localSiderealDegrees);
  const epsilon = degreesToRadians(obliquityDegrees);
  return window.ElectionalEphemeris.normalizeDegrees(
    radiansToDegrees(Math.atan2(Math.sin(theta) / Math.cos(epsilon), Math.cos(theta))),
  );
}

function calculateAscendant(localSiderealDegrees, latitudeDegrees, obliquityDegrees) {
  const theta = degreesToRadians(localSiderealDegrees);
  const latitude = degreesToRadians(latitudeDegrees);
  const epsilon = degreesToRadians(obliquityDegrees);
  const numerator = -Math.cos(theta);
  const denominator = Math.sin(theta) * Math.cos(epsilon) + Math.tan(latitude) * Math.sin(epsilon);

  return window.ElectionalEphemeris.normalizeDegrees(radiansToDegrees(Math.atan2(numerator, denominator)));
}

function getWholeSignHouse(longitude, ascendantLongitude) {
  const ascendantSign = Math.floor(window.ElectionalEphemeris.normalizeDegrees(ascendantLongitude) / 30);
  const bodySign = Math.floor(window.ElectionalEphemeris.normalizeDegrees(longitude) / 30);
  return ((bodySign - ascendantSign + 12) % 12) + 1;
}

function calculateAngles({ date, latitude, longitude }) {
  const localSiderealDegrees = getLocalSiderealDegrees(date, longitude);
  const obliquity = getObliquity(date);
  const ascendant = window.ElectionalEphemeris.normalizeDegrees(
    calculateAscendant(localSiderealDegrees, latitude, obliquity) + 180,
  );
  const midheaven = calculateMidheaven(localSiderealDegrees, obliquity);

  return [
    { ...ANGLE_DEFINITIONS[0], longitude: ascendant },
    { ...ANGLE_DEFINITIONS[1], longitude: midheaven },
    { ...ANGLE_DEFINITIONS[2], longitude: window.ElectionalEphemeris.normalizeDegrees(ascendant + 180) },
    { ...ANGLE_DEFINITIONS[3], longitude: window.ElectionalEphemeris.normalizeDegrees(midheaven + 180) },
  ].map((angle) => ({
    ...angle,
    zodiac: window.ElectionalEphemeris.getZodiacPosition(angle.longitude),
  }));
}

function getClosestAngle(planet, angles) {
  return angles
    .map((angle) => ({
      ...angle,
      distance: getAngleDistance(planet.longitude, angle.longitude),
    }))
    .sort((first, second) => first.distance - second.distance)[0];
}

function enrichPositionsWithHouses(positions, angles) {
  const ascendant = angles.find((angle) => angle.id === "asc");

  return positions.map((planet) => {
    const closestAngle = getClosestAngle(planet, angles);
    return {
      ...planet,
      house: getWholeSignHouse(planet.longitude, ascendant.longitude),
      closestAngle: {
        id: closestAngle.id,
        name: closestAngle.name,
        shortName: closestAngle.shortName,
        distance: closestAngle.distance,
      },
      isAngular: closestAngle.distance <= ANGULAR_ORB,
    };
  });
}

function getAngularityScore(positions) {
  return positions.reduce((score, planet) => {
    if (!planet.isAngular) {
      return score;
    }

    const closeness = Math.max(1, ANGULAR_ORB - planet.closestAngle.distance);

    if (BENEFIC_BODIES.has(planet.name)) {
      return score + 7 + closeness;
    }

    if (CHALLENGING_BODIES.has(planet.name)) {
      return score - 5 - closeness;
    }

    return score + 2;
  }, 0);
}

function formatAngle(angle) {
  return `${angle.shortName} ${window.ElectionalEphemeris.formatZodiacPosition(angle.zodiac)}`;
}

function formatAngleDistance(distance) {
  const degrees = Math.floor(distance);
  const minutes = Math.round((distance - degrees) * 60);
  return `${degrees} deg ${String(minutes).padStart(2, "0")} min`;
}

window.ElectionalHouses = {
  ANGULAR_ORB,
  calculateAngles,
  enrichPositionsWithHouses,
  formatAngle,
  formatAngleDistance,
  getAngularityScore,
};
