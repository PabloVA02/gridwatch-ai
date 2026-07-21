"""Print a deterministic telemetry payload that can be sent to the API."""

import json
import math
from datetime import UTC, datetime, timedelta


def build_payload(points: int = 72) -> dict:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    readings = []
    for index in range(points):
        hour = index % 24
        energy = 38 + 8 * math.sin(2 * math.pi * hour / 24)
        temperature = 23 + 2 * math.sin(2 * math.pi * hour / 24)
        if index in {31, 58}:
            energy *= 3.2
            temperature += 28
        readings.append(
            {
                "device_id": "factory-line-a",
                "observed_at": (start + timedelta(hours=index)).isoformat(),
                "energy_kwh": round(energy, 3),
                "voltage": 230 + (index % 3) - 1,
                "temperature_c": round(temperature, 2),
            }
        )
    return {"readings": readings}


if __name__ == "__main__":
    print(json.dumps(build_payload(), indent=2))
