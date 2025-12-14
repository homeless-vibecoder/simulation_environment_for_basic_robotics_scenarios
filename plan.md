We want to create a good environment for simulating robot(s) scenarios.
We do everything in 2D and visualize from the top - that really simplifies a lot of things (3D is just not worth the pain).

## Rough structure and goal




## Lowest level mechanics and properties

    - world, and environment
        - ability to insert characters, environment
        - environment should be able to have some available tools, mostly to make a field/put physical stuff
            - however, it could also have more out-of-box attributes - e.g. a place/square that sends a certain signal/magnetism that is only received by a certain radio (specific code, frequency, etc. - like aruco/qr code)
    - robot
        - a construction/composite that has an associated program, as well as parts - sensors, motors, connections, some other attributes

## Basic environment tools

First, note that the environment tools aren't necessarily for the students to mess with - I currently don't see an easy way students could create their own custom maps.
Instead, let us focus on what we need from the environment so that it is easy to write simulations.
No need to worry about speed - simplicity takes priority (and also, we don't expect convoluted scenarios).

A possibility is to have objects in environment that have associated properties, including location, visual effects, interaction with other things, etc.
It is hard to say apriori what all of the useful properties are, so it would be nice if we could define some of them (especially the niche ones) on the fly.


    - center (translation - where it is)
    - scale (one by default)
    - points (relative to the center) whose convex hull is the region of this object (and maybe a bounding triangle/box for simple/quick checks of contact)
        - probably useful to assume: things can only interact if they intersect
    - visual aspect/color
    - interaction
        - friction and traction
            - perhaps also include viscosity/damping
        - secret code/invisible fields
        - blockage: whether or not something can pass through it (e.g. maybe define different classes of blockage/interaction, and each object has an array of them - if there is a commmon element, two objects cannot pass through each other)
        - reflectivity (for distance sensor)
    - boolean variable: can_move. If true, information/characteristics of "moving things" should be provided

### connection

    - type of connection (or its rigidity)...
    - anchor points

### moving things

    - moment of inertia/mass


### visuals

    - wheels should have an arrow to indicate the spin

### Idea
    
    - have a ranking of strength to determine scenarios where unstoppable force meets immovable object
        - force
        - rigidity/strength of connection

## Interaction of objects

### When do objects interact

To make it easy, we say, objects interact only if they intersect.
In addition, we have some simple intersection checks (bounding triangle, bbox, etc. to avoid overcomputation - also to be able to say - if two centers are farther apart than the bounding triangle sizes, no need to check intersection - good for logn sort and local/adjacent element comparison)

### How objects interact

Both objects have their attributes (friction, velocity, mass, etc.) that can be used to calculate their interaction.
We also need a function that determines how some properties of an object - location, velocity, etc. - change, given the contact between two objects.
Note, there might be extra considerations to take, instead of just doing instantenous interaction - maybe similar to how gyro/accelerometer work - we have larger time-scale interaction, and we have smaller time-scale determined by different equations, and our final "fusion" is smaller time-scale quick response, with a dirft towards larger time-scale prediction.



## Basic robot tools

This is to build robots with specific sensors, physical properties, code (computation, lag), etc.


### Sensors and motors

### Building mechanics


## Dec 6 plan:

- Think of a systematic way of making the gui - perhaps use pre-built one or webots inspiration, etc.
- Think of a few scenarios to have a specific goal
maybe for next milestone also, include a vscode-like experience

## Dec 7 plan:

when selecting a motor/imu, etc. be able to drag/move it, similar to a point
mark the center of the robot.
By default, make everything rigid unless specified otherwise.
add cntrl Z to undo and redo.
device placements aren't easy.
add wheels icon/shape for motor/wheel.
allow for 

allow to select multiple points to edit - to rotate things, translate, etc.
Take inspiration from drawing apps.

Add colors and rounded colors for nicer visuals.

configuration of the buttons must be adjusted - it seems too goofy, perhaps there should be comparmentalization/modularity of functionality - not it seems everything is just exposed and messy.
There should be an ability to close some tabs/make them smaller (drag, expand, shrink, etc.)
drag and pan is reversed.


Could you make that text different format - code-like (mmonosspace) fonr would be more appropriate. It doesn't need to show all the time - it can be togglable/dropdown menu. Also, could you add some viewing options to the screen, so that I can scroll out, for exaple in order to zoom in/out and to translate. 
The current gui is too exposed - everything is there, and there is no depth (nothing is hidden, so it is a bit convoluted and lacks functionality). I want to have ability to view state of the motors/sensors. I also want to be able to time-log them, etc (actually, put that in the plan - previously I thought the time-logger would be. part of the robot design, but now I think it would be better to be built-in the viewer/runner/simulator). Also, I feel like the control user has from the siulation isn't enough - there is ability to edit the program of the robot, but insstructions aren't that clear, and they cannot edit, for example how the simulation goes - e.g. it would be nice if they could drag the robot so that it starts from a different positiion - convenient things like that - the flexibility is lacking. Too few things are available to do in the pygame window, and the reason is that everyhting is exposed - there are no drop-down menus that allows one to access many things. Your context window is getting full, so I am planning to switch to a new chat. Please write these plans - what we want to do for next steps, perhaps update @planning_the_gui.md , and give me prompt for the next chat - I will be using plan mode. Thanks!

Dec 7 runner polish (implemented now)
- Collapsible tabs (Code / Devices / State / Logs) with sidebar hide/show to reduce clutter.
- In-viewport view dropdown for reset/center, grid toggle, motor arrows toggle, and quick reposition entry.
- State tab shows live motors/sensors and a selectable logger (pick signals, rate, duration) with CSV export.
- Reposition tool lets you drag/set the robot start pose; reset to spawn or save current pose as new spawn.
- View controls normalized: wheel zoom, middle/right pan (fixed direction), optional grid.


Add the plotter and etc as a window - be able to select the .csv log and be able to open the plotting/analysis window.

Round to 2-3 decimal places when showing numbers. e.g. imu doesn't need to get printed exactly.

Make it clearer - how to edit the robot code - have a "help" option that describes how to alter code, and what format is expected, what sensors/motors there are.
Define/comment what sim means, roughly how it works - it should be accessible from "help" - all the clear instructions on how to use the program, examples, etc. Currently it is very unintuitive.
There should be definitions - what is function step() used for what is _apply(), how are all these things utilized in the simulation - what functions need to be defined, etc.
"Help" is very important and it should open up an elaborate README-like explanation.
On one hand, it should be very short, fast, and easy guide, but it should refer to different chapters.
For example, when someone opens "help" and opens the insturctions, a user has to be able to navigate to the appropriate chapter e.g. "how to get and set values of sensors/motors", or "what functions need to be defined in the class, and how they are used in the simulation", or "general overview of how the simulation works", or "how simulation works - physics, etc. - more in-depth guide/explanation".

Be able to pick a file to edit/control algorithm, so that one can have different control algorithms and switch between them.

Add a designer of the environment - might be useful to be able to draw on the floor (could be drawing as a visual effect or even drawing a wall).
UI very similar to paint.


Improve visuals of the wheels and arrows.

Be able to resize windows from any corner, not just the right corner


## Dec 8 plan:

### Understanding/clarity/user-friendlyness aspect

Add help section in runner that explains how to use everything and is a good overview of how things work.
Make it clearer - how to edit the robot code - have a "help" option that describes how to alter code, and what format is expected, what sensors/motors there are (remember, a beginner who has no clue how the code works, and who doesn't want to read the actual code, must be able to utilize all of the functionality).
Define/comment what sim means, roughly how it works - it should be accessible from "help" - all the clear instructions on how to use the program, examples, etc. Currently it is very unintuitive.
There should be definitions - what is function step() used for what is _apply(), how are all these things utilized in the simulation - what functions need to be defined, etc.
"Help" is very important and it should open up an elaborate README-like explanation.
On one hand, it should be very short, fast, and easy guide, but it should refer to different chapters.
For example, when someone opens "help" and opens the insturctions, a user has to be able to navigate to the appropriate chapter e.g. "how to get and set values of sensors/motors", or "what functions need to be defined in the class, and how they are used in the simulation", or "general overview of how the simulation works", or "how simulation works - physics, etc. - more in-depth guide/explanation".

Also, include clear instructions on file arrangement and how to create/delete new control algorithms, logs, etc.

Designer.py isn't really clear - how it works (what is body vs motors - how to interactions/collisions happen - what does it mean to place motor that is disconnected from the body, etc.). Its ui might get a lot of inspiration from the runner? Not sure about this one. For now, don't worry too much. It is good for what it is. It would be better to add more flexibility - e.g. paint-like thing for creating/drawing objects - e.g. in environment they might create visuals, as well as on a robot - maybe user wants drawinig something to understand orientation. Maybe the drawing/shapes have some properties - e.g. what if the user wants to make that the bounding region of the robot, etc. The flexibility would be nice.

### Physics and the simulation

Currently doesn't seem to respect tire traction, and instead uses forces to move the body. Instead, tire traction should be there. If we spin tire with some amount, if the tire doesn't end up with that velocity, there is traction happening, the traction isn't only lateral. If wheel spins at 0.1 m/s, but ends up moving 0.2 m/s there must be a lot of force/slippage. This doesn't seem to be taken care of.


### Add (necessary/extra) features

Add a designer of the environment - might be useful to be able to draw on the floor (could be drawing as a visual effect or even drawing a wall).
UI very similar to paint.
Note, the environment design might be a mode in the designer.py - since designer is just for designing and saving objects. Technically, any object could be defined there (custom), except with robot/environment, we can have a more conventient gui than for others.
Also, the environment should have an ability to have bound, so that robot never leaves a certain region.

Be able to pick a file to edit/control algorithm, so that one can have different control algorithms and switch between them.

Add the plotter and etc as a window - be able to select the .csv log and be able to open the plotting/analysis window.

### Visual aspect

Round to 2-3 decimal places when showing numbers. e.g. imu doesn't need to get printed exactly.
In runner, the state window is good, but I don't like the buttons of start logging, export log, etc. it is a bit convoluted (just like the ui at the beginning of this project). Instead, turn them into a drop-down menu like options so that they don't cover each-other and aren't too convoluted.

In panels/devices, there is extra text in top small rectangle ("show device help" button" - just completely remove that thing) - it has a relatively big font and seems useless, so remove it. Also, instead of just listing Motors: left_motor, right_motor, number them in bullet-point like format to make it clearer, and use bigger font for headers (or say, Available devices:, etc.). I like the control basics (examples) that show how to get a value. Maybe more improvements along that direction would be nice, also specifying what field in the controller class is expecting these things (some of that information will be in helper also, but here it would be nice to have a good summary, so that not everyone has to go to "help" to understand it).

Brush up the options - for example, currently view doesn't seem super useful - reset view, center robot, etc. are useless, since they can be done with a mouse anyway. What does seems useful though, is toggle motor arrows, toggle readings (up to 2 decimal places), etc. - things/helpers that sometimes might come in handy. For example, showing traversed path or some useful thing like that would be nice to have.
Not sure what format code does - perhaps remove. Also, loading multiple codes from the saved files should be done from here, I think, and to navigate between a few codes/files at the same time. This code section could be very helpful.
Snapshots, loading them should have more options. Keep the current one, but also have the option to "save as" where user names the snapshot, and another loading option which allows them to pick the appropriate one from the folder of snapshots (it should be drop-down menu, so imagine you hover over the button and to the right of it opens a view - just like we currently have with options - mac-like ui. Also include the robustness that we currently have - the tabs upon hover not closing instantly).

add wheels icon/shape for motor/wheel
Improve visuals of the wheels and arrows.

Maybe: have ability to rotate the view: if we press shift, and drag the enviroment/ground, the camera view rotates. Also, maybe include that we can shift+drag the robot to rotate (in help - how to use/ui section).

Add colors and rounded colors for nicer visuals.



## Milestone 2

Here, we need to add specific environments, robotics scenarios, robots, sample codes, interactive/keyboard control (sample programs for the robots so user can "play" with the robot and move it around as in a video-game - maybe also intructions on how to access not only the sensor readings and motors, but also keys pressed on the computer).


Maybe??? also add specific motors, sensors, servos, etc. (specific models with reasonable tunes).


## Four agents' work and further comments

### For designer.py

Very good work. There are a few additions that would be nice.

In designer, please add cmd+Z to be undo, also for drawing. Make it simpler and more united to easily switch between select/add and draw - those things should be close by in the menu, and currently, it is very difficult to switch between them or understand when there is drawing mode - preferably, add some ui to indicate drawing. Perhaps, for picking a brush, there should be a separate window/tab that opens once you click draw. The general interactions also need some updates e.g. when we go to draw mode, we dont have to reclick it every time to draw different sections - it should be similar to paint. We should also be able to draw shapes (e.g. rectangle, triangle), and then, the drawing should be able to be treated like an object - so, if we go advanced, we can attribute different properties to it (or maybe it is better to have the designs of complicated objects in a separate mode). We should be able to, not only add the devices present currently, but also to customize (so, if a user creates their own object, they should be able to use it here - perhaps allow to add a new object and go into the custom design mode - allow for a different tab/environment for that). Also, maybe have these designs/customs stored (with name, etc), and be able to import them from files (to search them, etc.).
Note, when designing the robot, the drawings should stay on the robot - as if all the connections when designing a robot are rigit.

Another thing, there should be two separate modes for creating a robot vs creating an environment: those two have completely different uses. We should have "create robot" or "create environment" or "create custom", and in create custom, there can be creation of different things, ability to add classes (e.g. attribute mass, etc). Currently, it isn't clear what should be included, but certainly, robot creationg and environment creation are separate, since when we export a robot, we export everything we did. So, please make 

Also, have an ability to add a new file, as opposed to just picking one.

Please also add option to go into details/advanced view (e.g. for a motor), where you can tune everything - perhaps code opens up, with all the necessary fields, etc. specified.

Also, it would be nice if we could rotate the environment (e.g. by shift+drag to rotate objects or environment).


#### For runner.py

In capture, loading specific snapshot shouldn't be the defualt view: if we hover over a button, then it should open up the further break-up of the files.
Also, the logger has a similar problem: not all should be visible under capture - there should be more nestedness/hierarchy into what gets opened.

Repositioning robot mode isn't neceessary - user can just drag it. The separate mode is difficult to turn on/off. Also, some unnecessary things should be taken out. Reposition robot as a separate button is unnecessary.

Capture has some functionality that should actually be in run. Continuing from a certain snapshot shuold be in run. Also, there is no need to say, start from spawn (as a separate button). Snapshots give enough generality.

Also, the imu doesn't show very well - it doesn't display numbers, instead it displays set. Please fix that and round the numbers to some decimal.

#### For the help section

Very good. Only a few things: some parts need better organization - more spacing e.g. in edit and switch controllers, it shouldn't just be a block of text - it should have less homogenous/monotonous feel to it. Feel free to use bullet points, titles with different sizes/fonts.

Also, there can be more information: not everything has to be a paragraph. There have to be short summaries and quick how-to convenient guides, but there should also be an option to read further.

Controllers need more explanation - what function does the simulation expect, what gets run, perhaps with an example or two.

Things need more explanations. e.g. what even is logging - the terms aren't trivial to understand - they should have (simple, dummed down almost) explanations for what they are, and

It would also be nice, if there were a more "supportive view" or analysis of the code - to visualize what the current code does. Not entirely sure if this is a good idea though.

## 
In Runner, can we click on the motors and stuff to see their status/behavior?
Add the plotter and etc as a window - be able to select the .csv log and be able to open the plotting/analysis window.

Designer:
double-click on file should select it - pressing ok isn't always necessary.
Different tabs for environment/robot/scenario aren't necessary, since we, at each time, might be editing a robot, witohut it being attached to any environment/scenario. So, those things should be completely separate. - this is an importnt change
In devices, there is no need to have "Place device". Also, there should be option to import or add devices that have been defined/saved (this can be done by having a button/option of view in folder, and then there should be an option to add a device from folder in the "working memory" of devices, so that it can be easily picked in general).
Brushes/drawing doesn't work - gives an error. We need a proper paint UI for painting - tab should open, whenever we are equiped with a pen.
Also, I don't see a reason to have the "Scenario" menu - whats the point? If we want to edit a certain scenario, we import/open it just like any other file (whether it's robot/environmen/scenario we are editing doesnt matter. We still either open a file/project or create a new one).

## Later milestone - would be nice: add exercises as scenarios

## End of day summary
1) Currently, what doesn't work is, the controller code is very unintuitive - how to use it etc.
    - multiple robot scenarios don't run
    - help isn't helpful
2) Designer has problems: drawing is very strange, and drawing walls crashes. The custom empty canvas which allows you to start project, for some reason, doesn't work - it is simple thing I am asking for - just an ability to open/create file as if we are working on a project. Then, the ability to export that. It is not that difficult - very common framework - as if we are editing a paint file or a CAD file - we just create a project, and edit whatever. Then, we can export if needed. I don't understand what is so hard about it.
3) Controller is very strange - I don't understand how it works, and the whole framework/structure needs to be understood and rewritten correctly.


## Dec 11

### Structural changes we need
1) We are able to store, as one file
    - tools/motors/sensors, etc.
    - robot with a controller (the code)
    - environment/canvas
    - scenario
The important thing is, in designer, we open files separately.
So, imagine each file, whether it is a robot or a scenario, is just a file/project.
We can open it and work on it.
This is different from a current version - currently, robot, environment, scenario are somehow attached, and this is NOT what we want.
Similar to how a CAD file can be opened and edited, we should be able to edit a file with the same editor - whether there is robot in the file or environment or scenario or something else, is irrelevant - the filestructure is the same.
That being said, in the storage - when we store the files, we should have a folder/file system, so that a user can pick where to save a project - in robot folder, scenario folder, etc.
Each file/project has a collection of things in it. When we import theses files/projects to other files, the objects get combined.
For example, if we have a robot 

Robot design is attached to its controller/code. The code can be altered from the runner as well.

2) the python file/code that is displayed in runner shouldn't be the whole python file - rather, we need to break up the code, so that the user, when they open code, has multi-tab view - one tab is soley responsible for the code at each iteration - the step() function (as opposed to them having to find the function and alter in-place), there should be one with initialization, one for imports, one for extra helper functions, one for just help tab - to say what attributes/motors/sesnsors are possible, etc.
The tabs should have names that are intuitive to understand, and on top, there should be description that "this code/snippet is for ...".

Next step refinement for the code:
    - attach the code to the robot: currently it seems, the code has nothing to do with the robot, even if I delete the whole code, the robot's behavior doesn't change.
    - simplify the codes/programs
    - have the extra notes/helper buttons an option to open, but closed by default - not exposed
    - confirm that program/coding works and robot actually implements the code, and correctly. Test that the simulation is also accurate. Test thoroughly and be critical - if there is a difficulty or possibilty of a certain part being not user-friendly, make it user-friendly.