*This project has been created as part of the 42 curriculum by <login>.*

# Fly-in

## Description

This project simulates a fleet of drones moving from one start hub to one end hub through a graph of connected hubs.
It follows the Fly-in subject requirements: object-oriented Python, strict parsing, turn-based simulation, movement costs for restricted zones, capacity checks for hubs and links, and visual feedback. The subject explicitly requires minimizing total turns, respecting zone and link capacities, handling restricted zones as 2-turn moves, and providing a visual representation. fileciteturn0file0

The current version improves the movement logic compared with a simple greedy next-hop approach. Instead of only taking one static shortest hop and waiting when that single hop is blocked, the scheduler scores all currently available neighbors using weighted distance-to-goal, priority-zone bonus, backtracking penalty, link load, and target occupancy. This better matches the subject requirement that drones should move simultaneously, avoid unnecessary delays, distribute across multiple paths, and adapt to different topologies. fileciteturn0file0turn0file4turn0file6

## Project structure

- `fly_in/models.py` — core dataclasses
- `fly_in/parser.py` — strict parser with clear errors
- `fly_in/pathfinding.py` — reusable planner and reverse-distance cache
- `fly_in/simulator.py` — turn scheduler and movement engine
- `fly_in/renderer.py` — pygame visualizer with drone numbers
- `fly_in/main.py` — entry point
- `maps/` — ready-to-use challenge maps

## Instructions

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Run the visual simulator:

```bash
python3 -m fly_in.main maps/easy/01_linear_path.txt --auto --log
```

Controls:

- `SPACE` play/pause
- `N` next turn
- `R` reset
- `ESC` exit

## Algorithm choices

The subject asks for an algorithm that minimizes turns, handles simultaneous movement, respects occupancy and connection rules, and treats restricted zones as multi-turn travel. fileciteturn0file0

This implementation uses these ideas:

1. **Reverse weighted distance cache**  
   A planner computes the weighted distance from every hub to the end once, using zone-entry costs. This gives each drone a stable idea of what “closer to the goal” means.

2. **Dynamic local scheduling**  
   Each turn, idle drones are ordered by remaining estimated distance. For each drone, the scheduler evaluates all currently legal neighbors and chooses the best one instead of blindly following one precomputed path.

3. **Congestion-aware scoring**  
   Candidate hops are penalized when the target hub is already crowded or when the link is already heavily used. This helps spread drones across multiple valid routes.

4. **Loop resistance**  
   Going back to the immediately previous hub gets a penalty, so drones do not oscillate in loops unless that is really the only good move.

5. **Restricted-zone transit**  
   Entering a restricted hub takes 2 turns. During transit, the drone stays on the connection, the connection remains occupied, and the log outputs the connection name until arrival, matching the mandatory output rules. fileciteturn0file0

## Visual representation

The subject allows colored terminal output or a graphical interface. This project uses a graphical pygame view that shows:

- hub colors from the map metadata
- link capacities
- highlighted busy links
- drone numbers drawn on each drone
- current turn, delivered count, and movement log

That directly supports the required “visual feedback” part of the assignment. fileciteturn0file0turn0file5

## Resources

- Fly-in subject PDF: `/mnt/data/fly_in.pdf`
- Python documentation
- Pygame documentation

## AI usage

AI was used to help reorganize the project structure, improve the scheduling logic, write cleaner README text, and package the provided maps into a ready-to-run project. The final code should still be reviewed, tested, and explained by the student.
