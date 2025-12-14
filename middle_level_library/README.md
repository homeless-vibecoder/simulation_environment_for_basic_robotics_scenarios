# Middle-Level Library

This package collects reusable robotics primitives that sit between the low-level physics (simulation_environment/low_level_mechanics) and higher-level demos.

## Modules
- base.py: shared abstractions for sensors/motors/noise.
- sensors.py: plug-and-play line array, distance, and IMU sensors.
- motors.py: simple and detailed wheel motors plus DifferentialDrive.
- robots.py: blueprints like DemoLineFollower that assemble a chassis, sensors, and actuators.
- presets.py: named parameter sets matching typical hardware for students to import.

## Extending
Derive from the base classes and make sure to call SimObject.apply_force(..., application_point=...) so offset forces produce torque. Add new presets whenever you model additional hardware so exercises can pull configurations by name.
