"""Main CLI tool to use the AWBW Replay Parser libraries"""

import argparse
import glob
import gzip
import logging
import sys
from collections import defaultdict

from awbw_replay.awbw import AWBWGameAction, AWBWGameState
from awbw_replay.replay import AWBWReplay

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

# These are just random names for cleaner viewing.
PLAYER_NAMES = ["Alice", "Bob", "Colin", "Drake", "Eagle", "Flak", "Grit", "Hawke"]

LOGGING_LEVELS = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]


def get_args(argv=None):
    """
    Handles argument parsing for main

    Arguments:
    - argv: List of string arguments, or None to use sys.argv (default)

    Returns:
    - namespace containing parsed arguments
    """

    parser = argparse.ArgumentParser(description="AWBW Replay Parser tool")

    parser.add_argument("files", help="Replay file to open", type=str, nargs='+')
    parser.add_argument(
            "--verbose",
            "-v",
            help="Set the logging verbosity",
            type=str,
            default="WARNING",
            choices=LOGGING_LEVELS)

    return parser.parse_args(argv)


def dump_end_of_day_funds(replay):
    """Parses a replay to generate plots of data"""
    states = [AWBWGameState(replay_initial=replay.game_info())]

    # Generate all the states
    ## States are the way the game looked as the turn ended
    for action in replay.actions():
        # Get the action
        action = AWBWGameAction(replay_action=action)
        message = [
            f"turn: {states[-1].game_info['turn']}",
            f"action_number: {len(states)}",
            f"action_type: {action.type}",
        ]
        logging.debug(" ".join(message))
        # Apply the action to the latest game state
        states.append(states[-1].apply_action(action))

    players = {}
    for p_id, player in states[-1].players.items():
        players[p_id] = {"name": "Loser " if player["eliminated"] else "Winner", "funds": []}

    # For each state, get the day. If it's the last state of the day, track both player's stats
    day = 1
    for i, state in enumerate(states):
        if i + 1 >= len(states) or states[i+1].game_info["day"] == day + 1:
            for p_id, player in players.items():
                player["funds"].append(state.players[p_id]["funds"])
            day += 1
    logging.info("End of day funds:")
    for player in players.values():
        logging.info(player['name'] + " " + str(player['funds']))


def calc_firing_coords(replay: AWBWReplay, attackers_coords: defaultdict, defenders_coords: defaultdict):
    """Parses a replay to generate coordinates where firing happens"""
    states = [AWBWGameState(replay_initial=replay.game_info())]

    # Generate all the states
    # States are the way the game looked as the turn ended
    for action in replay.actions():
        # Get the action
        action = AWBWGameAction(replay_action=action)
        if action.type == AWBWGameAction.Type.FIRE:
            action_infos = action.info[AWBWGameAction.Type.FIRE.value]['combatInfoVision']
            # Each fire action seems to have 2 entries (1 for each player?)
            # Take the one that has visibility into both the attacker and the defender
            for action_info in action_infos.values():
                if isinstance(action_info['combatInfo']['attacker'], dict) and isinstance(action_info['combatInfo']['defender'], dict):
                    attackers_coords[
                        (action_info['combatInfo']['attacker']['units_x'],
                         action_info['combatInfo']['attacker']['units_y'])] += 1
                    defenders_coords[
                        (action_info['combatInfo']['defender']['units_x'],
                         action_info['combatInfo']['defender']['units_y'])] += 1
                    break
                else:
                    continue
        # Apply the action to the latest game state
        states.append(states[-1].apply_action(action))


def print_coord_frequencies(coords_frequencies):
    if len(coords_frequencies) == 0:
        logging.warning("Skipping due to no coordinates")
        return
    max_value = max(coords_frequencies.values())
    max_value_digit_length = len(str(max_value))
    max_x_coord = max(map(lambda k: k[0], list(coords_frequencies.keys())))
    max_y_coord = max(map(lambda k: k[1], list(coords_frequencies.keys())))
    out = ""
    for x in range(max_x_coord):
        out += "|"
        for y in range(max_y_coord):
            value = coords_frequencies[(x, y)]
            out += str(value).rjust(max_value_digit_length, ' ')
            out += ", "
        out += "|\n"
    print(out)


def print_attackers_defenders_coords(attackers_coords: defaultdict, defenders_coords: defaultdict):
    sorted_attackers_coords = sorted(attackers_coords.items(), key=lambda kv: kv[1], reverse=True)
    sorted_defenders_coords = sorted(defenders_coords.items(), key=lambda kv: kv[1], reverse=True)

    print("Attacking coords:")
    coords_str = ""
    for coord, count in sorted_attackers_coords:
        coords_str += str(coord) + " " + str(count) + ";"
    print(coords_str)
    print("Defending coords:")
    coords_str = ""
    for coord, count in sorted_defenders_coords:
        coords_str += str(coord) + " " + str(count) + ";"
    print(coords_str)

    print_coord_frequencies(attackers_coords)
    print_coord_frequencies(defenders_coords)


def main(args):
    """Handles the CLI args to call analyze one or more replays"""
    # TODO: Define a custom logger to individually control the logging level of our modules
    logging.basicConfig(level=args.verbose)

    attackers_coords = defaultdict(int)
    defenders_coords = defaultdict(int)
    for file_glob in args.files:
        logging.info("Processing file glob %s", file_glob)
        for filename in glob.iglob(file_glob):
            logging.info("Opening %s", filename)
            try:
                with AWBWReplay(filename) as replay:
                    #dump_end_of_day_funds(replay)
                    calc_firing_coords(replay, attackers_coords, defenders_coords)
            except gzip.BadGzipFile as e:
                logging.error("Could not open replay %s: %s", filename, e)
    print_attackers_defenders_coords(attackers_coords, defenders_coords)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main(get_args()))
