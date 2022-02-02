# -*- coding: utf-8 -*-

import cgi
from html import escape
import random
import string
import threading
import time
from flask import redirect, render_template, request
from app import app, socketio
from flask_socketio import join_room, leave_room
import schedule


from posio.game import Game
from .game_master import GameMaster

# The max distance used to compute players score
SCORE_MAX_DISTANCE = app.config.get('SCORE_MAX_DISTANCE')

# The time given to a player to answer a question
MAX_RESPONSE_TIME = app.config.get('MAX_RESPONSE_TIME')

# The time between two turns
TIME_BETWEEN_TURNS = app.config.get('TIME_BETWEEN_TURNS')

# The time between two turns
NUMBER_OF_TURNS = app.config.get('NUMBER_OF_TURNS')

# How many answers are used to compute user score
LEADERBOARD_ANSWER_COUNT = app.config.get('LEADERBOARD_ANSWER_COUNT')

# Are players allowed to give multiple answers to the same question
ALLOW_MULTIPLE_ANSWER = app.config.get('ALLOW_MULTIPLE_ANSWER')

# How many zoom level are allowed
ZOOM_LEVEL = min(app.config.get('ZOOM_LEVEL'), 2)

# CDN Url for static ressources
CDN_URL = app.config.get('CDN_URL')


# Dictionary of current games
games: dict[str, GameMaster] = {}


@app.route('/')
def home():
    letters = string.ascii_lowercase
    game_id = ''.join(random.choice(letters) for i in range(10))
    return redirect("/game/" + game_id, code=302)


@app.route('/game/<game_id>')
def render_game(game_id):
    return render_template('game.html',
                           MAX_RESPONSE_TIME=MAX_RESPONSE_TIME,
                           LEADERBOARD_ANSWER_COUNT=LEADERBOARD_ANSWER_COUNT,
                           ALLOW_MULTIPLE_ANSWER=ALLOW_MULTIPLE_ANSWER,
                           ZOOM_LEVEL=ZOOM_LEVEL,
                           CDN_URL=CDN_URL)


@socketio.on('join_game')
def join_game(game_id: str, player_id: str, player_name):
    app.logger.info('{player_name} has joined the game {game_id}'.format(
        player_name=player_name, game_id=game_id))

    game_id = escape(game_id)
    player_id = escape(player_id)
    player_name = escape(player_name)

    if game_id not in games:
        # Create the game master and start the game
        games[game_id] = GameMaster(game_id,
                                    SCORE_MAX_DISTANCE,
                                    LEADERBOARD_ANSWER_COUNT,
                                    MAX_RESPONSE_TIME,
                                    TIME_BETWEEN_TURNS,
                                    NUMBER_OF_TURNS)
        games[game_id].start_game()

    # Add the player to the game
    join_room(game_id)
    join_room(request.sid)
    games[game_id].game.add_player(request.sid, player_id, player_name)
    games[game_id].on_join()


@socketio.on('disconnect')
def leave_games():
    app.logger.info('A player has left the game')
    for game_id in games:
        games[game_id].game.remove_player(request.sid)
        leave_room(game_id)
        leave_room(request.sid)


@socketio.on('play_again')
def play_again(game_id):
    app.logger.info('A player has left the game')
    if game_id in games:
        games[game_id].play_again()


@socketio.on('answer')
def store_answer(game_id, latitude, longitude):
    app.logger.info('Player {request} has answered for game {game_id} {latitude} {longitude}'.format(
        request={request.sid}, game_id=game_id, latitude=latitude, longitude=longitude))

    game_id = escape(game_id)

    if game_id in games:
        app.logger.info("Game exists")
        games[game_id].game.store_answer(request.sid, latitude, longitude)


# Run check in bagkground thread https://schedule.readthedocs.io/en/stable/background-execution.html
def run_continuously(interval=1):
    """Continuously run, while executing pending jobs at each
    elapsed time interval.
    @return cease_continuous_run: threading. Event which can
    be set to cease continuous run. Please note that it is
    *intended behavior that run_continuously() does not run
    missed jobs*. For example, if you've registered a job that
    should run every minute and you set a continuous run
    interval of one hour then your job won't be run 60 times
    at each interval but only once.
    """
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.daemon = True
    continuous_thread.start()
    continuous_thread.join(1)
    return cease_continuous_run


def background_job():
    print("checking for old games")
    for game_id in list(games.keys()):
        print(games[game_id].game.total_online())
        if games[game_id].game.total_online() == 0:
            print("Deleting old game", game_id)
            del games[game_id]


schedule.every().hour.do(background_job)

# Start the background thread
stop_run_continuously = run_continuously()
