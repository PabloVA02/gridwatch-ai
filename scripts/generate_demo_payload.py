"""Print a deterministic telemetry payload that can be sent to the API."""

import argparse
import json
import math
from datetime import UTC, datetime, timedelta


def build_payload(
    points: int = 72,
    device_id: str = "factory-line-a",
    shift_after: int | None = None,
) -> dict:
    if points < 1:
        raise ValueError("points must be positive")
    if shift_after is not None and not 0 < shift_after < points:
        raise ValueError("shift_after must be between 1 and points - 1")

    start = datetime(2026, 7, 1, tzinfo=UTC)
    readings = []
    incident_indices = {31, 58}
    if shift_after is not None:
        incident_indices.update({shift_after + 37, shift_after + 173})
    for index in range(points):
        hour = index % 24
        energy = 38 + 8 * math.sin(2 * math.pi * hour / 24)
        temperature = 23 + 2 * math.sin(2 * math.pi * hour / 24)
        if shift_after is not None and index >= shift_after:
            energy *= 1.25
            temperature += 4
        if index in incident_indices:
            energy *= 3.2
            temperature += 28
        readings.append(
            {
                "device_id": device_id,
                "observed_at": (start + timedelta(hours=index)).isoformat(),
                "energy_kwh": round(energy, 3),
                "voltage": 230 + (index % 3) - 1,
                "temperature_c": round(temperature, 2),
            }
        )
    return {"readings": readings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", type=int, default=72)
    parser.add_argument("--device-id", default="factory-line-a")
    parser.add_argument("--shift-after", type=int)
    arguments = parser.parse_args()
    print(
        json.dumps(
            build_payload(arguments.points, arguments.device_id, arguments.shift_after),
            indent=2,
        )
    )
