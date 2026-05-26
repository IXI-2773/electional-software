const LOCATION_PRESETS = {
  "los-angeles": {
    name: "Los Angeles, CA",
    latitude: 34.0522,
    longitude: -118.2437,
    timezone: "America/Los_Angeles",
  },
  "new-york": {
    name: "New York, NY",
    latitude: 40.7128,
    longitude: -74.006,
    timezone: "America/New_York",
  },
  london: {
    name: "London, UK",
    latitude: 51.5074,
    longitude: -0.1278,
    timezone: "Europe/London",
  },
  paris: {
    name: "Paris, France",
    latitude: 48.8566,
    longitude: 2.3522,
    timezone: "Europe/Paris",
  },
  tokyo: {
    name: "Tokyo, Japan",
    latitude: 35.6762,
    longitude: 139.6503,
    timezone: "Asia/Tokyo",
  },
  sydney: {
    name: "Sydney, Australia",
    latitude: -33.8688,
    longitude: 151.2093,
    timezone: "Australia/Sydney",
  },
};

function parseDateParts(date, time) {
  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute] = (time || "09:00").split(":").map(Number);

  return { year, month, day, hour, minute };
}

function getTimeZoneOffset(date, timezone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);

  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const asUtc = Date.UTC(
    Number(values.year),
    Number(values.month) - 1,
    Number(values.day),
    Number(values.hour),
    Number(values.minute),
    Number(values.second),
  );

  return asUtc - date.getTime();
}

function zonedTimeToUtc(date, time, timezone) {
  const parts = parseDateParts(date, time);
  let utcTime = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, 0);

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const offset = getTimeZoneOffset(new Date(utcTime), timezone);
    utcTime = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, 0) - offset;
  }

  return new Date(utcTime);
}

function formatInTimezone(date, timezone) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

window.ElectionalTimezone = {
  LOCATION_PRESETS,
  formatInTimezone,
  zonedTimeToUtc,
};
