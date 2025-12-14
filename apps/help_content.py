"""Structured help + menu specs for the runner UI."""
from __future__ import annotations

from typing import Dict, List

# Shared numeric rounding policy for UI displays.
ROUNDING_DIGITS = 2

# Help topics are intentionally lightweight and linear so they can be rendered
# in a scrollable overlay and snapshotted in tests.
HELP_TOPICS: List[Dict[str, object]] = [
    {
        "id": "quickstart",
        "title": "Quick start",
        "lines": [
            "Summary: pick a scenario, run, tweak controller, repeat.",
            "Quick steps:",
            "- Scenario > name > Load; Run > Play/Pause or Step.",
            "- Edit controller.py in Code; Save + Reload to apply.",
            "- Capture > Snapshots for quick saves; Run > Resume from snapshot.",
            "- Capture > Logging to start/stop and export CSV; State panel shows live signals.",
            "",
            "Deeper checks:",
            "- Logs panel lists errors; clear before rerun.",
            "- Panel menu toggles Code/State/Logs/Plot; View holds grid/motor arrow toggles.",
        ],
    },
    {
        "id": "controllers",
        "title": "Edit and switch controllers",
        "lines": [
            "Summary: controller files live next to robot.json/world.json; Controller menu switches modules.",
            "Quick how-to:",
            "- Duplicate controller.py -> rename (controller_pid.py, etc.) -> edit class Controller.",
            "- Controller menu entry selects module; Save + Reload applies code.",
            "- Keep snapshots/logs in the scenario folder to compare changes.",
            "",
            "Switching details:",
            "- robot.json sets controller_module; menu entries map to controller_*.py files.",
            "- Keep imports lightweight; avoid long blocking calls inside step().",
            "",
            "Example shape:",
            "- class Controller(sim):",
            "-     def __init__(self, sim): self.turn = 0.0  # optional setup",
            "-     def step(self, sensors, dt):",
            "-         heading = sensors.get('imu', {}).get('ang', 0.0)",
            "-         sim.motors['left'].command(0.5 - 0.1 * heading, sim, dt)",
            "-         sim.motors['right'].command(0.5 + 0.1 * heading, sim, dt)",
            "-     def reset(self): self.turn = 0.0",
        ],
    },
    {
        "id": "required-fns",
        "title": "Required functions",
        "lines": [
            "Summary: implement Controller(sim) with step(sensors, dt) issuing motor commands only.",
            "Expectations:",
            "- step(...) runs every sim tick with sensor dict + dt.",
            "- Use sim.motors['name'].command(value, sim, dt); sim handles _apply().",
            "- Optional hooks: __init__ for setup, reset() for warm starts; keep loops finite.",
            "- Use sim.dt and sim.time; sim.last_sensor_readings / last_motor_commands aid debugging.",
            "",
            "Guidance:",
            "- Keep outputs bounded; avoid blocking sleeps; prefer incremental adjustments.",
            "- Raise exceptions rarely; errors pause the sim until cleared in Logs.",
        ],
    },
    {
        "id": "sensors-motors",
        "title": "Sensors and motors",
        "lines": [
            "Summary: sensors supply latest readings; motors take commands you issue.",
            "Sensors:",
            "- sensors['name'] returns latest value; IMU yields {'ang': yaw, 'lin': (vx, vy)} rounded in UI.",
            "- Encoders expose .value; distance/line sensors expose .value or tuples depending on model.",
            "Motors:",
            "- sim.motors['name'].command(speed, sim, dt) sets wheel speed/force; clamped for stability.",
            "- Keep commands modest and consistent; sudden spikes destabilize physics.",
            "Visibility:",
            "- Devices panel lists hardware; logger toggles any motor:/sensor: signal for CSV/plots.",
        ],
    },
    {
        "id": "simulation",
        "title": "Simulation loop",
        "lines": [
            "Each step: read sensors -> call controller step() -> integrate physics -> contacts.",
            "Top-down mode zeroes gravity; friction/traction come from robot.json materials.",
            "dt comes from world.json timestep; wheel traction and max speed are clamped.",
            "Snapshots freeze bodies, joints, devices, and controller state for reproducible reruns.",
            "Errors pause the sim; open Logs to inspect and clear before resuming.",
        ],
    },
    {
        "id": "logging-snapshots",
        "title": "Logging, export, snapshots",
        "lines": [
            "Summary: logging records selected signals to CSV; snapshots freeze sim state.",
            "Logging basics:",
            "- Capture > Logging > Start/Stop to record motor:/sensor: signals at chosen rate/duration.",
            "- Export log writes CSV; Plot panel or Open CSV plotter visualizes columns.",
            "- Logging = time-stamped numeric samples; IMU shows yaw/accel rounded to 2 decimals.",
            "",
            "Snapshots:",
            "- Capture > Snapshots for quick save or Save as...",
            "- Run > Resume from snapshot lists recent files and Load from file for other saves.",
            "- Snapshots store world, robot, controller state for deterministic reruns.",
            "",
            "Supportive/analysis note:",
            "- State panel shows live signals + logger toggles; future analysis overlays can build on it.",
        ],
    },
]

# Menu labels we want to keep stable for tests and screenshots.
CAPTURE_MENU_STRUCTURE: Dict[str, List[str]] = {
    "Snapshots": ["Quick snapshot", "Save snapshot as..."],
    "Logging": [
        "Start/Stop logging",
        "Export log",
        "Open CSV plotter",
        "Show plot panel",
        "Clear plot",
        "Logger rate 120 Hz",
        "Logger rate 60 Hz",
        "Logger rate 30 Hz",
        "Logger rate 10 Hz",
        "Logger duration 5 s",
        "Logger duration 15 s",
        "Logger duration 60 s",
        "Logger duration Unlimited",
    ],
}
CAPTURE_MENU_LABELS: List[str] = list(CAPTURE_MENU_STRUCTURE.keys())


def serialize_help_topics() -> List[Dict[str, object]]:
    """Return a serializable copy of the help topics for tests."""
    return [
        {"id": t["id"], "title": t["title"], "lines": list(t.get("lines", []))}
        for t in HELP_TOPICS
    ]


def serialize_capture_menu() -> Dict[str, object]:
    """Expose capture/logging menu labels and rounding for deterministic checks."""
    return {
        "capture_labels": list(CAPTURE_MENU_LABELS),
        "capture_structure": {section: list(items) for section, items in CAPTURE_MENU_STRUCTURE.items()},
        "rounding_digits": ROUNDING_DIGITS,
    }
