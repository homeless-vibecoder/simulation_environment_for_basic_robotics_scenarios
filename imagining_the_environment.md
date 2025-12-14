This document is for describing what I want the simulation to look like, so that one can get the gist, without me specifying all the details.

## Building a robot

There is going to be some chasis built (including types of connections), perhaps with an importance score on constrains (e.g. two points stay the same distance - constrain importance score directly translates to lagrange multipliers).
On the chasis, there will be motors (separate objects), as well as sensors (fixed to some place).
So, there will be some "dead" parts, as well as the "alive/electronics" parts.
That being said, there is no need to worry about it being hyper-realistic by including breadboards and computers (we can just name the motors/sensors and get their readings/commands from the robot code).

Sensors have a significance - objects can have some attributes that the sensor measures.
For example, an object/region can have an attribute color: black.
Then, the light sensor will interact with it a certain way.

Robot has a program/code.
It is almost like writing a character for a game: the sensors and motors determine the commands/moves, while the robot program uses them (e.g. robot.motor_1 = 0.5 for setting speed of motor).

A user/student would create an occurence of a class/robot, and would use that specific robot in some environment.


## Robot's interaction with the world

The robot is properly simulated, including the sensors, motors, etc.
It might be a good idea to have lagrange-multiplier like satisfaction of constrains, as well as a configurable accuracy vs speed of the simulation (almost like timestep).


## Ease of use

Every utility and function is in a folder.
The folder student works in is separate and only has code that imports the design of some robot

There are . different folders:
1) utilities (low-level mechanics, fundamental stuff, etc. - this includes everything necessary, including visualization, all necessary classes)
2) collection of pre-configured sensors, motors, chasis (uses utilities to define objects/sensors and motors so that their performance matches the performance of real sensors and motors, etc.).
3) another folder, which contains two folders: robots and worlds/enviroments
    - robots has robot designs, specifically, it uses the sensors, motors, chases to build it
    - enviroments has different enviroments: I'm not entirely sure about the details for this one
    - NOTE: each robot/enviroment must have a description for what it is and how to use it. Also, note that the format needn't be python. It might be better to just store the values in json or something like that and build the actual object when importing.
4) 

There is a list of pre-configured robots with explanations, as well as pre-configured controllers with explanations.
