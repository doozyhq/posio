# -*- coding: utf-8 -*-

import sqlite3
import os
from math import sqrt, pi
from collections import namedtuple

Answer = namedtuple('Answer', ['latitude', 'longitude'])
Result = namedtuple('Result', ['distance', 'score'])


DIR_PATH = os.path.dirname(os.path.abspath(__file__))

# Earth ellipsoid equator length in meters
EARTH_EQUATOR = 6378137.0

# Convert degrees to kilometres
DISTANCE_PER_DEGREE = (2 * pi * EARTH_EQUATOR) / (360 * 1000)


class Game:
    def __init__(self, score_max_distance, leaderboard_answer_count):
        self.score_max_distance = score_max_distance
        self.leaderboard_answer_count = leaderboard_answer_count
        self.cities = self.get_cities()
        self.players: dict[str, Player] = {}
        self.turn_number = 0
        self.is_turn_happening = False

    def player_exits(self, player_sid):
        return player_sid in self.players

    def add_player(self, player_sid, player_id, player_name):
        if player_id in self.players:
            self.players[player_id].sid = player_sid
            self.players[player_id].set_is_online(True)
            self.players[player_id].set_name(player_name)
        else:
            self.players[player_id] = Player(
                player_sid, player_id, player_name)

    def remove_player(self, player_sid):
        # Get the player corresponding to the given sid and mark them offline
        for player_id in self.players:
            if self.players[player_id].sid == player_sid:
                self.players[player_id].set_is_online(False)
                self.players[player_id].set_sid(None)

    def total_online(self):
        total = 0

        for player_id in self.players:
            total += self.players[player_id].is_online

        return total

    def start_new_turn(self):
        self.is_turn_happening = True
        # Update turn number
        self.turn_number += 1

    def get_current_city(self):
        # Return a different city for each turn
        return self.cities[self.turn_number % len(self.cities)]

    def store_answer(self, player_sid, latitude, longitude):
        print("Storing answer")
        # Get the player corresponding to the given sid
        for player_id in self.players:
            if player_sid == self.players[player_id].sid:
                # Store player answer
                answer = Answer(latitude, longitude)
                self.players[player_id].add_answer(self.turn_number, answer)

    def end_current_turn(self):
        self.is_turn_happening = False
        current_city = self.get_current_city()

        # Compute scores for each player
        for player in [player for player_sid, player in self.players.items() if player.has_answered(self.turn_number)]:  # noqa
            # Get the distance between player answer and correct answer
            player_answer = player.get_answer(self.turn_number)
            distance = self.plane_distance(current_city['latitude'],
                                           current_city['longitude'],
                                           player_answer.latitude,
                                           player_answer.longitude)

            # Compute player score for this answer
            score = self.score(distance)

            # Store player result for this turn
            result = Result(distance, score)
            player.set_result(self.turn_number, result)

    def get_current_turn_ranks(self):
        # Get players who have played this turn
        current_turn_players = [player for player_sid, player in self.players.items() if player.has_played(self.turn_number)]  # noqa

        # Sort players based on their scores on this turn
        ranked_players = sorted(
            current_turn_players,
            key=lambda player: player.get_result(self.turn_number).score,
            reverse=True)

        return ranked_players

    def get_ranked_scores(self):
        # Get scores for each players
        oldest_turn = 0
        scores_by_player = {
            player_sid: player.get_global_score(oldest_turn, self.turn_number)
            for player_sid, player in self.players.items()}

        # Rank the scores of players
        ranked_scores = [{
            'player': self.players[player_sid],
            'score': scores_by_player[player_sid]
        } for player_sid in sorted(self.players,
                                           key=lambda player_sid: scores_by_player[player_sid],  # noqa
                                           reverse=True)]

        return ranked_scores

    def score(self, distance):
        # Convert distance to a score
        score = self.score_max_distance - distance

        # Score cannot be negative
        return max(0, round(score))

    @staticmethod
    def get_cities():
        # Connect to the city database
        conn = sqlite3.connect(os.path.join(DIR_PATH, '../data/cities.db'))

        # Select every cities in random order
        c = conn.cursor()

        c.execute('SELECT name, country, latitude, longitude FROM cities ORDER BY RANDOM()')  # noqa

        cities = []
        for name, country, latitude, longitude in c.fetchall():
            cities.append({
                'name': name,
                'country': country,
                'latitude': latitude,
                'longitude': longitude
            })

        # Close connection
        conn.close()

        return cities

    @staticmethod
    def plane_distance(latitude1, longitude1, latitude2, longitude2):
        # Calculates distance as points on a plane (faster than Haversine)
        px = longitude2 - longitude1
        py = latitude2 - latitude1
        return sqrt(px * px + py * py) * DISTANCE_PER_DEGREE


class Player:
    def __init__(self, sid: str, user_id: str, name: str):
        self.sid = sid
        self.user_id = user_id
        self.is_online = True
        self.name = name
        self.answers = {}
        self.results = {}
        self.sessions = []

    def add_answer(self, turn, answer):
        self.answers[turn] = answer

    def has_answered(self, turn):
        return turn in self.answers

    def get_answer(self, turn):
        return self.answers[turn]

    def set_result(self, turn, score):
        self.results[turn] = score

    def set_is_online(self, online):
        self.is_online = online

    def set_sid(self, sid):
        self.dif = sid

    def set_result(self, turn, score):
        self.results[turn] = score

    def set_name(self, name: str):
        self.name = name

    def has_played(self, turn):
        return turn in self.results

    def get_result(self, turn):
        return self.results[turn]

    def get_global_score(self, start_turn, end_turn):
        return sum(result.score for turn, result in self.results.items() if start_turn < turn <= end_turn)  # noqa

    def __hash__(self):
        return hash(self.sid)

    def __eq__(self, other):
        return self.sid == other.sid
