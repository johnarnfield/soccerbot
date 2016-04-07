import re
import shelve
import requests
import os
import textwrap


data = shelve.open("/tmp/footy")
if 'players' not in data:
    data['players'] = []
if 'date' not in data:
    data['date'] = None
if 'limit' not in data:
    data['limit'] = None
if 'teams' not in data:
    data['teams'] = [[], []]
usercache = {}


def footy_set_date(date, limit=None):
    data['date'] = date
    data['players'] = []
    data['limit'] = limit
    data['teams'] = [[], []]
    if limit is not None:
        return "Next game set for {}, limited to {} players".format(date, limit)
    return "Next game set for {}".format(date)


def footy_add_player(username):
    if not data['date']:
        return "There are no upcoming games"
    if username in data['players']:
        return "{} is already down to play on {}".format(username, data['date'])
    if data['limit'] and len(data['players']) >= data['limit']:
        return "The game on {} has enough players already".format(data['date'])
    data['players'] = data['players'] + [username]
    return "{} is now playing in the game on {}".format(username, data['date'])


def footy_remove_player(username):
    if not data['date']:
        return "There are no upcoming games"
    num_players_before = len(data['players'])
    data['players'] = [player for player in data['players'] if player != username]
    num_players_after = len(data['players'])
    if num_players_before != num_players_after:
        return "{} is no longer playing in the game on {}".format(username, data['date'])
    else:
        return "{} is not down to play in the game on {}".format(username, data['date'])


def footy_set_team(username, team):
    if not data['date']:
        return "There are no upcoming games"
    if username not in data['players']:
        return "{} is not down to play in the game on {}".format(username, data['date'])
    data['teams'] = [[player for player in team if username != player] for team in data['teams']]
    data['teams'][team - 1] += [username]
    return "{} added to team {}".format(username, team)


def footy_set_teams(team_a, team_b):
    if not data['date']:
        return "There are no upcoming games"
    for player in team_a + team_b:
        if player not in data['players']:
            return "{} is not down to play on {}".format(player, data['date'])
    data['teams'] = [team_a, team_b]
    teams = " vs ".join([", ".join(team) for team in data['teams']])
    return "The teams are {}".format(teams)


def footy_get():
    if not data['date']:
        return "There are no upcoming games"
    information = ["Next game set for {}".format(data['date'])]
    if any(data['teams']):
        teams = " vs ".join([", ".join(team) for team in data['teams']])
        information.append("The teams are {}".format(teams))
        unallocated_players = set(data['players']) - set([player for team in data['teams'] for player in team])
        if len(unallocated_players) > 1:
            information.append("{} have not been assigned teams".format(
                ", ".join(unallocated_players)))
        elif len(unallocated_players) == 1:
            information.append("{} has not been assigned a team".format(
                list(unallocated_players)[0]))
    else:
        if not data['players']:
            information.append("Nobody is yet down to play")
        else:
            information.append("{} {} playing".format(
                ", ".join(data['players']),
                "is" if len(data['players']) == 1 else "are"))
    return "\n".join(information)


def footy_done():
    if not data['date']:
        return "There are no upcoming games"
    data['date'] = None
    data['players'] = []
    return "Game removed"


def footy_help():
    return textwrap.dedent("""\
        ```
        !footy [OPTION]

        Options:
            help                    Print this help
            set <date> [<limit>]    Set the date of the next game, optionally changing
                                    the maximum number of players (default: 10)
            done                    End the current game
            join                    Join the next game
            leave                   Leave the next game
            add <username>          Add the user to the next game
            remove <username>       Remove the user from the next game
            team <player> [12]      Add the user to either team 1 or 2
            teams <username[, username]> vs <username[, username]>  Set the teams

        With no options provided, outputs the details of the current game
        ```
    """)


def footy_join(username):
    if not data['date']:
        return "There are no upcoming games"
    if username in data['players']:
        return "You're already down to play on {}".format(data['date'])
    if data['limit'] and len(data['players']) >= data['limit']:
        return "The game on {} has enough players already".format(data['date'])
    data['players'] = data['players'] + [username]
    return "You're now down to play in the game on {}".format(data['date'])


def footy_leave(username):
    if not data['date']:
        return "There are no upcoming games"
    if username not in data['players']:
        return "You're not down to play on {}".format(data['date'])
    data['players'] = filter(lambda player: player != username, data['players'])
    return "You're no longer down to play in the game on {}".format(data['date'])


def get_username(user):
    if user not in usercache:
        response = requests.post('https://slack.com/api/users.info', data={
            'token': os.environ.get("SLACK_TOKEN"),
            'user': user
        }).json()
        usercache[user] = response['user']['name']
    return usercache[user]


def on_message(msg, server):
    text = msg.get("text", "")
    match = re.match(r"!footy( .*)?", text)
    if not match:
        return

    command = (match.group(1) or "").strip()

    # set <date>
    match = re.match(r"^set (.+?)(\s(\d+))?\s*$", command)
    if match:
        date = match.group(1)
        limit = match.group(3)
        return footy_set_date(date, int(limit) if limit is not None else 10)

    # add <username>
    match = re.match(r"^add (.+)", command)
    if match:
        return footy_add_player(match.group(1))

    # remove <username>
    match = re.match(r"^remove (.+)", command)
    if match:
        return footy_remove_player(match.group(1))

    # teams <name[, name ...]> vs <name[, name ...]>
    match = re.match(r"^teams (.+) vs (.+)", command)
    if match:
        teams = [re.findall("[a-z0-9][a-z0-9._-]*", team) for team in [match.group(1), match.group(2)]]
        return footy_set_teams(*teams)

    # team <name> <side>
    match = re.match(r"^team (.+) ([12])", command)
    if match:
        return footy_set_team(match.group(1), int(match.group(2)))

    # join
    match = re.match(r"^join", command)
    if match:
        return footy_join(get_username(msg['user']))

    # leave
    match = re.match(r"^leave", command)
    if match:
        return footy_leave(get_username(msg['user']))

    # done
    match = re.match(r"^done", command)
    if match:
        return footy_done()

    # help
    match = re.match(r"^help", command)
    if match:
        return footy_help()

    return footy_get()
