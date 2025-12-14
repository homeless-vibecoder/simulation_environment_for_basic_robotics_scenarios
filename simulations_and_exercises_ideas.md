## The goal

The goal is to generate a good/pleasant interactive/visual simulations/exercises, where students can experiment with different codes under different robotics situations.

This could also serve as an intermediate environment between book/paper and harsh, harsh reality.

They should be VERY user-friendly:
    - runnable without complicated imports
    - unrelated/ugly parts stored separately
    - for each simulation/situation, there should be a good readme file, explaining how to use the program/simulation, and an example usage

The simulations could take a form of
    - writing code for the "character" and running/observing it in a simulation
    - engaging in a more interactive real-time coding/tuning in GUI and seeing the results
    - adverserial game to mke control algorithms robust against a certain noise/opponent which applies a force in a certain pattern (e.g. periodic of some unknown periodicity, etc.)

Allow use of sensor measurement and also access to real value (useful for stategizing - is it good heuristic to use?, in ideal case, would this work?, etc. +  easier troubleshooting).
Note: this environment can teach students troubleshooting. If we make troubleshooting in the simulation nicer (no import difficulties, etc, just to go straight to the heart of the problem), yet realistic, we will teach a very useful skill.

Use random seeds (and explain what they are) - to allow for reproducability, yet pseudorandomness.

Maybe: allow construction of robots also - have some simple method to design line follower robot (where are the wheels, sensors, any other sensors?)?
This would be super helpful for creating custom environment also.


## Ideas

### Control arc, filters, state, etc.
    - Design a robot (e.g. line follower)
        - in ice
        - storm
        - etc. different environments
    - Rocket control
    - Adversarial control (one designs noise/disturbance, other defends it)
    - Flappy bird <-> discretized control, perhaps vary discretization, and write a control algorithm that plays it well

### Filter - signal processing
    - Tangible - maybe knobs good enough, or if something more interactive.....??

### Geometry?
