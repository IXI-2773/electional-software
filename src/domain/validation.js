const JPL_REFERENCE_CHART = {
  label: "JPL Horizons geocentric check",
  date: "2026-05-26",
  time: "09:00",
  timezone: "America/Los_Angeles",
  latitude: 34.0522,
  longitude: -118.2437,
  source: "NASA/JPL Horizons API quantity 31",
  bodies: [
    { name: "Sun", longitude: 65.4227709, latitude: -0.0001104 },
    { name: "Moon", longitude: 193.2197266, latitude: -3.1370201 },
    { name: "Mercury", longitude: 79.3441892, latitude: 1.8759469 },
    { name: "Venus", longitude: 99.0799794, latitude: 1.8134227 },
    { name: "Mars", longitude: 35.794371, latitude: -0.6769639 },
    { name: "Jupiter", longitude: 113.0784982, latitude: 0.4079127 },
    { name: "Saturn", longitude: 11.7781417, latitude: -2.2425681 },
    { name: "Uranus", longitude: 61.7537567, latitude: -0.1599985 },
    { name: "Neptune", longitude: 3.9515232, latitude: -1.3364408 },
    { name: "Pluto", longitude: 305.4179244, latitude: -4.1265644 },
  ],
};

const LONGITUDE_TOLERANCE_DEGREES = 0.04;
const ANGLE_SANITY_REFERENCE = {
  label: "Los Angeles morning angle sanity",
  expectedAscendantSign: "Cancer",
  expectedMidheavenSign: "Aries",
};
const SWISS_EPHEMERIS_ANGLE_REFERENCE = {
  label: "Swiss Ephemeris Whole Sign angles",
  source: "sweph-wasm 2.6.9 / swe_houses(..., 'W')",
  ascendant: 110.13511832023705,
  midheaven: 6.5293592412573105,
  tolerance: 0.05,
};

function getSignedLongitudeDelta(actual, expected) {
  const delta = window.ElectionalEphemeris.normalizeDegrees(actual - expected);
  return delta > 180 ? delta - 360 : delta;
}

function runJplValidation() {
  const chartDate = window.ElectionalTimezone.zonedTimeToUtc(
    JPL_REFERENCE_CHART.date,
    JPL_REFERENCE_CHART.time,
    JPL_REFERENCE_CHART.timezone,
  );
  const actualPositions = window.ElectionalEphemeris.getPlanetPositions(chartDate);

  const bodies = JPL_REFERENCE_CHART.bodies.map((reference) => {
    const actual = actualPositions.find((position) => position.name === reference.name);
    const longitudeDelta = getSignedLongitudeDelta(actual.longitude, reference.longitude);
    const latitudeDelta = actual.latitude - reference.latitude;

    return {
      name: reference.name,
      actualLongitude: actual.longitude,
      expectedLongitude: reference.longitude,
      longitudeDelta,
      latitudeDelta,
      pass: Math.abs(longitudeDelta) <= LONGITUDE_TOLERANCE_DEGREES,
    };
  });

  const maxLongitudeDelta = Math.max(...bodies.map((body) => Math.abs(body.longitudeDelta)));

  return {
    ...JPL_REFERENCE_CHART,
    bodies,
    maxLongitudeDelta,
    pass: bodies.every((body) => body.pass),
    tolerance: LONGITUDE_TOLERANCE_DEGREES,
  };
}

function runAngleSanityValidation() {
  const chartDate = window.ElectionalTimezone.zonedTimeToUtc(
    JPL_REFERENCE_CHART.date,
    JPL_REFERENCE_CHART.time,
    JPL_REFERENCE_CHART.timezone,
  );
  const angles = window.ElectionalHouses.calculateAngles({
    date: chartDate,
    latitude: JPL_REFERENCE_CHART.latitude,
    longitude: JPL_REFERENCE_CHART.longitude,
  });
  const ascendant = angles.find((angle) => angle.id === "asc");
  const midheaven = angles.find((angle) => angle.id === "mc");
  const descendant = angles.find((angle) => angle.id === "dsc");
  const ic = angles.find((angle) => angle.id === "ic");
  const ascDscDistance = window.ElectionalAspects.getAngularDistance(ascendant.longitude, descendant.longitude);
  const mcIcDistance = window.ElectionalAspects.getAngularDistance(midheaven.longitude, ic.longitude);

  return {
    ...ANGLE_SANITY_REFERENCE,
    ascendant,
    midheaven,
    ascDscDistance,
    mcIcDistance,
    pass:
      ascendant.zodiac.sign === ANGLE_SANITY_REFERENCE.expectedAscendantSign &&
      midheaven.zodiac.sign === ANGLE_SANITY_REFERENCE.expectedMidheavenSign &&
      Math.abs(ascDscDistance - 180) < 0.0001 &&
      Math.abs(mcIcDistance - 180) < 0.0001,
  };
}

function runSwissAngleValidation() {
  const chartDate = window.ElectionalTimezone.zonedTimeToUtc(
    JPL_REFERENCE_CHART.date,
    JPL_REFERENCE_CHART.time,
    JPL_REFERENCE_CHART.timezone,
  );
  const angles = window.ElectionalHouses.calculateAngles({
    date: chartDate,
    latitude: JPL_REFERENCE_CHART.latitude,
    longitude: JPL_REFERENCE_CHART.longitude,
  });
  const ascendant = angles.find((angle) => angle.id === "asc");
  const midheaven = angles.find((angle) => angle.id === "mc");
  const ascendantDelta = getSignedLongitudeDelta(ascendant.longitude, SWISS_EPHEMERIS_ANGLE_REFERENCE.ascendant);
  const midheavenDelta = getSignedLongitudeDelta(midheaven.longitude, SWISS_EPHEMERIS_ANGLE_REFERENCE.midheaven);

  return {
    ...SWISS_EPHEMERIS_ANGLE_REFERENCE,
    ascendant,
    midheaven,
    ascendantDelta,
    midheavenDelta,
    pass:
      Math.abs(ascendantDelta) <= SWISS_EPHEMERIS_ANGLE_REFERENCE.tolerance &&
      Math.abs(midheavenDelta) <= SWISS_EPHEMERIS_ANGLE_REFERENCE.tolerance,
  };
}

window.ElectionalValidation = {
  ANGLE_SANITY_REFERENCE,
  JPL_REFERENCE_CHART,
  LONGITUDE_TOLERANCE_DEGREES,
  SWISS_EPHEMERIS_ANGLE_REFERENCE,
  runAngleSanityValidation,
  runJplValidation,
  runSwissAngleValidation,
};
