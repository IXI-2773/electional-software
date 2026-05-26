const PYTHON_BACKEND_BASE_URL = "http://127.0.0.1:8765";
let pythonBackendUnavailableUntil = 0;

async function fetchWithTimeout(url, options = {}, timeoutMs = 900) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
  }
}

async function scorePositions({ presetId, aspects, positions }) {
  if (Date.now() < pythonBackendUnavailableUntil) {
    throw new Error("Python backend is temporarily unavailable.");
  }

  try {
    const response = await fetchWithTimeout(`${PYTHON_BACKEND_BASE_URL}/api/score`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ presetId, aspects, positions }),
    });

    if (!response.ok) {
      throw new Error(`Python backend returned ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    pythonBackendUnavailableUntil = Date.now() + 5000;
    throw error;
  }
}

window.ElectionalPythonBackend = {
  baseUrl: PYTHON_BACKEND_BASE_URL,
  scorePositions,
};
