# Fly-in pygame starter

## Run

```bash
pip install -r requirements.txt
python -m fly_in.main maps/01_linear_path.txt --auto
```

## Controls

- SPACE - play/pause
- N - next turn
- R - restart map
- ESC - quit

## Notes

- `restricted` zones take 2 turns to enter.
- `blocked` zones are ignored.
- path choice is greedy and capacity-aware, so it is a good starter, not a perfect optimizer.
