# Time And Simulation Research

This folder collects primary references on time semantics, time management, and
clock models across simulation, emulation, distributed simulation, and related
systems.

The goal is not to privilege one simulator's worldview. It is to understand the
cross-domain concepts that tend to recur whenever a system needs to express:

- simulated or logical time versus wall-clock time
- event ordering and causality
- timeouts, deadlines, cadence, and latency
- episodic reset and replay
- synchronization between simulation and external or real-time systems

## Archived PDFs

- `jefferson-1987-time-warp-operating-system.pdf`
  - David Jefferson et al., "Distributed Simulation and the Time Warp Operating System"
- `misra-virtual-time-and-timeout-in-client-server.pdf`
  - Jayadev Misra, "Virtual Time and Timeout in Client-Server Networks"
- `taylor-sudra-hoffman-2003-time-management-cots-distributed-simulation.pdf`
  - Taylor, Sudra, and Hoffman, "Time management issues in COTS distributed simulation: a case study"
- `lee-thuente-sichitiu-2014-integrated-simulation-emulation-adaptive-time-dilation.pdf`
  - Hee Won Lee, David Thuente, and Mihail L. Sichitiu, "Integrated Simulation and Emulation Using Adaptive Time Dilation"
- `wainer-devs-report.pdf`
  - Yentl Van Tendeloo, "Activity-aware DEVS simulation"
- `pellegrini-2013-root-sim-tutorial.pdf`
  - Alessandro Pellegrini and Francesco Quaglia, "The ROme OpTimistic Simulator: A Tutorial"

## Online Primary References Consulted

- ROS 2 design: Clock and Time
  - <https://design.ros2.org/articles/clock_and_time.html>
- SimPy: Time and Scheduling
  - <https://simpy.readthedocs.io/en/4.0.2/topical_guides/time_and_scheduling.html>
- ns-3 manual: Realtime
  - <https://www.nsnam.org/docs/manual/html/realtime.html>
- FMI 3.0.2 specification
  - <https://fmi-standard.org/docs/3.0.2/>
- NASA technical report on time constraints in multi-rate federation executions
  - <https://ntrs.nasa.gov/api/citations/20250000321/downloads/TimeConstraints.pdf>
  - This PDF was reachable in-browser during research but timed out repeatedly
    when fetched from this environment.

## Recurrent Cross-Domain Concepts

- Multiple time domains or clocks often coexist.
- Time advancement policy is a first-class architectural choice.
- Ordering and causality rules matter independently of raw timestamps.
- Reset, episode, and replay boundaries are part of temporal semantics.
- Real-time pacing and simulation time are not interchangeable.
- Time disclosure and provenance are needed when results are compared across
  different realizations.
