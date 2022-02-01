# -*- coding: utf-8 -*-

import random
import string
from flask import redirect, render_template, request
from app import app, socketio
from flask_socketio import join_room, leave_room
from .game_master import GameMaster

# The max distance used to compute players score
SCORE_MAX_DISTANCE = app.config.get('SCORE_MAX_DISTANCE')

# The time given to a player to answer a question
MAX_RESPONSE_TIME = app.config.get('MAX_RESPONSE_TIME')

# The time between two turns
TIME_BETWEEN_TURNS = app.config.get('TIME_BETWEEN_TURNS')

# How many answers are used to compute user score
LEADERBOARD_ANSWER_COUNT = app.config.get('LEADERBOARD_ANSWER_COUNT')

# Are players allowed to give multiple answers to the same question
ALLOW_MULTIPLE_ANSWER = app.config.get('ALLOW_MULTIPLE_ANSWER')

# How many zoom level are allowed
ZOOM_LEVEL = min(app.config.get('ZOOM_LEVEL'), 2)

# CDN Url for static ressources
CDN_URL = app.config.get('CDN_URL')


# Dictionary of current games
games = {}


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
def join_game(game_id, player_name):
    app.logger.info('{player_name} has joined the game {game_id}'.format(
        player_name=player_name, game_id=game_id))

    if game_id not in games:
        # Create the game master and start the game
        games[game_id] = GameMaster(game_id,
                                SCORE_MAX_DISTANCE,
                                LEADERBOARD_ANSWER_COUNT,
                                MAX_RESPONSE_TIME,
                                TIME_BETWEEN_TURNS)
        games[game_id].start_game()

    # Add the player to the game
    join_room(game_id)
    join_room(request.sid)
    games[game_id].game.add_player(request.sid, player_name)


@socketio.on('disconnect')
def leave_games():
    app.logger.info('A player has left the game')
    for game_id in games:
        if games[game_id].game.player_exits(request.sid): 
            games[game_id].game.remove_player(request.sid)
            leave_room(game_id)
            leave_room(request.sid)


@socketio.on('answer')
def store_answer(game_id, latitude, longitude):
    app.logger.info('Player {request} has answered for game {game_id} {latitude} {longitude}'.format(
        request={request.sid},game_id=game_id, latitude=latitude, longitude=longitude))
    if game_id in games:
        app.logger.info("Game exists")
        games[game_id].game.store_answer(request.sid, latitude, longitude)
