"""Sample controller for the generic scenario."""


class Controller:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.left_target = 0.1
        self.right_target = 0.1

    def step(self, sensors, dt: float) -> None:
        # Basic line-follow: slow when distance sees obstacle
        dist = sensors.get("front_distance", None)
        line = sensors.get("line_array", None)
        if dist is not None and dist < 0.4 and False:
            self.left_target = 0.1
            self.right_target = 0.1
        elif isinstance(line, list) and len(line) >= 2 and False:
            error = (line[-1] - line[0]) if len(line) >= 2 else 0.0
            k = 0.5
            base = 0.4
            self.left_target = base - k * error
            self.right_target = base + k * error
        self.left_target = max(-1.0, min(1.0, self.left_target))
        self.right_target = max(-1.0, min(1.0, self.right_target))
        self._apply()

    def _apply(self) -> None:
        motor_left = self.sim.motors.get("left_motor")
        motor_right = self.sim.motors.get("right_motor")
        if motor_left:
            motor_left.command(self.left_target, self.sim, self.sim.dt)
        if motor_right:
            motor_right.command(self.right_target, self.sim, self.sim.dt)

    def get_state(self):
        return {"left": self.left_target, "right": self.right_target}

    def set_state(self, state):
        self.left_target = state.get("left", self.left_target)
        self.right_target = state.get("right", self.right_target)