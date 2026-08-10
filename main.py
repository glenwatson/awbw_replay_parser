"""Main CLI tool to use the AWBW Replay Parser libraries"""

import argparse
import logging
import sys
from collections import defaultdict
import re
from pathvalidate import sanitize_filepath
import os
import urllib.parse
import urllib.request
from typing import Dict, List

from awbw_replay.awbw import AWBWGameAction, AWBWGameState
from awbw_replay.replay import AWBWReplay

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

# These are just random names for cleaner viewing.
PLAYER_NAMES = ["Alice", "Bob", "Colin", "Drake", "Eagle", "Flak", "Grit", "Hawke"]

LOGGING_LEVELS = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]

logger = logging.getLogger(__name__)

def get_args(argv=None):
    """
    Handles argument parsing for main

    Arguments:
    - argv: List of string arguments, or None to use sys.argv (default)

    Returns:
    - namespace containing parsed arguments
    """

    parser = argparse.ArgumentParser(description="AWBW Replay Parser tool")

    parser.add_argument("--map-id", help="The awbw.amarriner.com maps_id", type=int)
    parser.add_argument("--download-directory", help="The path to store the replays", type=str)
    parser.add_argument(
            "--verbose",
            "-v",
            help="Set the logging verbosity",
            type=str,
            default="WARNING",
            choices=LOGGING_LEVELS)

    return parser.parse_args(argv)

def get_awbw_map_name(map_id: int):
    url = f"https://awbw.amarriner.com/prevmaps.php?maps_id={map_id}"
    with urllib.request.urlopen(url) as response:
        html = response.read().decode('utf-8')
    # Match href="prevmaps.php?maps_id=X">...</a>
    match = re.search(
        r'href="prevmaps.php\?maps_id='+str(map_id)+'">([^<]+)</a>',
        html, re.DOTALL)
    return match.group(1).strip() if match else None

def get_game_replay_urls(map_name: str):
    url = f"http://awbw.mooo.com/search?q={urllib.parse.quote(map_name)}"
    with urllib.request.urlopen(url) as response:
        html = response.read().decode('utf-8')
    # Match .dC > a: allow only whitespace between the opening .dC tag and the <a>
    relative_urls = re.findall(
        r'class="[^"]*\bdC\b[^"]*"[^>]*>\s*<a[^>]+href="([^"]*)"',
        html)
    return ["http://awbw.mooo.com/" + relative_url for relative_url in relative_urls]

def check_if_already_downloaded(url: str, directory: str):
    filename = os.path.basename(urllib.parse.urlparse(url).path)
    return os.path.exists(os.path.join(directory, filename))

def download_file_to_dir(url: str, directory: str):
    filename = os.path.basename(urllib.parse.urlparse(url).path)
    os.makedirs(directory, exist_ok=True)
    dest = os.path.join(directory, filename)
    urllib.request.urlretrieve(url, dest)

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


def calc_firing_coords(action: AWBWGameAction, attackers_coords: defaultdict, defenders_coords: defaultdict):
    """Generates coordinates where firing happens"""
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


def calc_move_coords(action: AWBWGameAction, move_coords: defaultdict):
    """Generates coordinates where units move"""
    if action.type == AWBWGameAction.Type.MOVE:
        key = 'global'
        # During FoW (fog) games, there is no 'global' view
        if key not in action.info['unit']:
            key = next(iter(action.info['paths'].keys()))
        unit_type = action.info['unit'][key]['units_name']
        for coord in action.info['paths'][key]:
            move_coords[unit_type][(coord['x'], coord['y'])] += 1


def add_attacking_days(action: AWBWGameAction, day: int, attacking_turn_counts: List[int]):
    """Counts the number of attacks on each day"""
    if action.type == AWBWGameAction.Type.FIRE:
        if day < len(attacking_turn_counts):
            attacking_turn_counts[day] += 1
        else:
            attacking_turn_counts.extend([0] * (day - len(attacking_turn_counts) + 1))
            attacking_turn_counts[day] = 1


def print_human_readable_coord_frequencies(coords_frequencies):
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

    # print_human_readable_coord_frequencies(attackers_coords)
    # print_human_readable_coord_frequencies(defenders_coords)


def print_unit_move_coords(unit_to_coord_to_freq: defaultdict):
    for unit_name in unit_to_coord_to_freq.keys():
        sorted_unit_to_coord_to_freq = sorted(unit_to_coord_to_freq[unit_name].items(), key=lambda kv: kv[1], reverse=True)

        print(unit_name + " coords:")
        coords_str = ""
        for coord, count in sorted_unit_to_coord_to_freq:
            coords_str += str(coord) + " " + str(count) + ";"
        print(coords_str)

        # print_human_readable_coord_frequencies(unit_to_coord_to_freq[unit_name])


def print_attacking_day_averages(attacking_day_counts: List[int], num_of_replays_processed: int):
    if num_of_replays_processed == 0:
        print("No replays processed")
        return
    for day, attack_count in enumerate(attacking_day_counts):
        print(format_day(day) + " had on average " + str(round(attack_count / num_of_replays_processed, 2)) + " attacks."
            " (" + str(attack_count) + " attacks / " + str(num_of_replays_processed) + " games)")
    print(str(sum(attacking_day_counts)) + " total attacks")


def format_day(day: int):
    # TODO assumes only 2 players
    return "Day " + str(round(day / 2) + 1) + "." + str(day % 2)


def main(args):
    """Handles the CLI args to call analyze one or more replays"""
    # Set up root logger for library modules; named logger for this module
    # allows each module's log level to be controlled independently.
    logging.basicConfig(level=args.verbose)
    logger.setLevel(args.verbose)

    map_name = get_awbw_map_name(args.map_id)
    if map_name is None:
        logger.error("No map found for %s", args.map_id)
        return EXIT_FAILURE
    logger.info("Map Name: %s", map_name)

    download_directory = sanitize_filepath(f"{args.download_directory if args.download_directory is not None else 'maps'}/{args.map_id}")
    logger.info("Download directory: %s", download_directory)
    map_replay_urls = get_game_replay_urls(map_name)
    logger.info("%s replay urls", len(map_replay_urls))
    for url in map_replay_urls:
        if not check_if_already_downloaded(url, download_directory):
            logger.info("Downloading %s to %s/", url, download_directory)
            download_file_to_dir(url, download_directory)
        else:
            logger.info("Already downloaded %s to %s/", url, download_directory)


    # Unit name -> coordinate -> frequency that unit moved across that coordinate
    unit_to_coord_to_freq = defaultdict(lambda: defaultdict(int))
    attackers_coords = defaultdict(int)
    defenders_coords = defaultdict(int)
    # turn (day) -> # of attacks on that day
    attacking_day_counts = []
    num_of_replays_processed_successfully = 0
    for filename in [file for file in os.listdir(download_directory) if file.lower().endswith('.zip')]:
        logger.info("Opening %s", filename)
        try:
            with AWBWReplay(os.path.join(download_directory, filename)) as replay:
                #dump_end_of_day_funds(replay)
                if replay.game_info()["maps_id"] != args.map_id:
                    logger.warning("Replay %s has maps_id %s, expected %s; skipping",
                                   filename, replay.game_info()["maps_id"], args.map_id)
                    continue
                states = [AWBWGameState(replay_initial=replay.game_info())]
                day = 0

                # Generate all the states
                # States are the way the game looked as the turn ended
                for action in replay.actions():
                    # Get the action
                    action = AWBWGameAction(replay_action=action)
                    # calculate things for this action
                    calc_move_coords(action, unit_to_coord_to_freq)
                    calc_firing_coords(action, attackers_coords, defenders_coords)
                    add_attacking_days(action, day, attacking_day_counts)

                    # progress the day
                    if action.type == AWBWGameAction.Type.END:
                        day += 1

                    # Apply the action to the latest game state
                    states.append(states[-1].apply_action(action))
                num_of_replays_processed_successfully += 1
        except Exception as e:
            logger.exception("Bad replay: %s", filename)
    print_unit_move_coords(unit_to_coord_to_freq)
    print_attackers_defenders_coords(attackers_coords, defenders_coords)
    print_attacking_day_averages(attacking_day_counts, num_of_replays_processed_successfully)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main(get_args()))
