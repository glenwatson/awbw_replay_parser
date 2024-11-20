"""Main CLI tool to use the AWBW Replay Parser libraries"""

import argparse
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

    parser.add_argument("file", help="Replay file to open", type=str)
    parser.add_argument(
            "--file-list",
            "-l",
            help="Treat file as a list of replays to open",
            action="store_true")
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


def dump_firing_coords(replay):
    """Parses a replay to generate coordinates where firing happens"""
    states = [AWBWGameState(replay_initial=replay.game_info())]

    # Generate all the states
    # States are the way the game looked as the turn ended
    attackers_coords = defaultdict(int)
    defenders_coords = defaultdict(int)
    for action in replay.actions():
        # Get the action
        action = AWBWGameAction(replay_action=action)
        if action.type == AWBWGameAction.Type.FIRE:
            action_infos = action.info[AWBWGameAction.Type.FIRE.value]['combatInfoVision']
            # Each fire action seems to have 2 entries (1 for each player?)
            # Take the one that has visibility into both the attacker and the defender
            for action_info in action_infos.values():
                if 'attacker' in action_info['combatInfo'] and 'defender' in action_info['combatInfo']:
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
    sorted_attackers_coords = sorted(attackers_coords.items(), key=lambda kv: kv[1], reverse=True)
    sorted_defenders_coords = sorted(defenders_coords.items(), key=lambda kv: kv[1], reverse=True)
    logging.info("Attacking coords:")
    for coord, count in sorted_attackers_coords:
        logging.info(str(coord) + " " + str(count))
    logging.info("Defending coords:")
    for coord, count in sorted_defenders_coords:
        logging.info(str(coord) + " " + str(count))


def main(args):
    """Handles the CLI args to call analyze one or more replays"""
    # TODO: Define a custom logger to individually control the logging level of our modules
    logging.basicConfig(level=args.verbose)

    if not args.file_list:
        with AWBWReplay(args.file) as replay:
            dump_end_of_day_funds(replay)
            dump_firing_coords(replay)
    else:
        logging.info("Running on a file list")
        replay_files = []
        with open(args.file, "r", encoding="utf-8") as file:
            for line in file:
                replay_files.append(line.strip())

        for filename in replay_files:
            logging.info("Opening %s", filename)
            try:
                with AWBWReplay(filename) as replay:
                    dump_end_of_day_funds(replay)
                    dump_firing_coords(replay)
            except gzip.BadGzipFile as e:
                logging.error("Could not open replay %s: %s", filename, e)
                continue

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main(get_args()))
