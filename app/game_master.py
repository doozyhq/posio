# -*- coding: utf-8 -*-

import threading
from app import socketio, app
from posio.game import Game


class GameMaster:
    """
    Starts the game and manages the game lifecycle
    """

    def __init__(self,
                 game_id,
                 score_max_distance,
                 leaderboard_answer_count,
                 max_response_time,
                 time_between_turns,
                 number_of_turns):
        """
        :param game_id: The id of this game
        :param score_max_distance: The distance above which player scores will be null
        :param leaderboard_answer_count: How many answers are used to compute user scores in the leaderboard
        :param max_response_time: The time given to a player to answer a question
        :param between_turns_duration: The time between two turns
        """
        self.game_id = game_id
        self.game = Game(score_max_distance, leaderboard_answer_count)
        self.max_response_time = max_response_time
        self.time_between_turns = time_between_turns
        self.number_of_turns = number_of_turns
        self.remaining_turns = number_of_turns
        self.lock = threading.Lock()

    def start_game(self):
        socketio.start_background_task(target=self.first_run)

    def first_run(self):
        # Give the players some time to answer
        socketio.sleep(self.max_response_time)
        self.run_game()

    def run_game(self):
        # Start the game
        while self.remaining_turns > 0:
            # Start a new turn
            self.start_turn()

            # Give the players some time to answer
            socketio.sleep(self.max_response_time)

            # End the turn
            self.end_turn()

            # Send the new leaderboard to players
            self.update_leaderboard()

            # Give the user some time between two turns
            socketio.sleep(self.time_between_turns)

    def start_turn(self):
        app.logger.debug('Starting new turn')

        # Start a new turn
        self.game.start_new_turn()

        # Get the city for this turn
        city = self.game.get_current_city()

        # Send the infos on the new city to locate to every players in the game
        socketio.emit(
            'new_turn',
            {
                'current_turn': {
                    'city': city['name'],
                    'country': city['country'],
                    'country_code': city['country'],
                },
                'remaining_turns': self.remaining_turns,
                'total_turns': self.number_of_turns
            },
            room=self.game_id
        )

        self.remaining_turns -= 1

    def on_join(self):
        if self.game.is_turn_happening == False and self.game.turn_number > 0:
            self.end_turn()
        self.update_leaderboard()

    def end_turn(self):
        app.logger.debug('Ending turn')

        # End current turn
        self.game.end_current_turn()

        # Rank answers
        ranked_players = self.game.get_current_turn_ranks()
        player_count = len(ranked_players)

        # Send end of turn signal and correct/best answers to players
        city = self.game.get_current_city()
        turn_results = {
            'correct_answer':
            {
                'name': city['name'],
                'lat': city['latitude'],
                'lng': city['longitude'],
            },
            'remaining_turns': self.remaining_turns,
            'total_turns': self.number_of_turns
        }

        if player_count > 0:
            best_result = ranked_players[0].get_result(self.game.turn_number)
            best_answer = ranked_players[0].get_answer(self.game.turn_number)
            turn_results['best_answer'] = {
                'distance': best_result.distance,
                'score': best_result.score,
                'lat': best_answer.latitude,
                'lng': best_answer.longitude,
                'player_name': ranked_players[0].name
            }
            turn_results['other_answers'] = []

            # Then send individual player results
            for rank, player in enumerate(ranked_players):
                if rank > 0:
                    result = player.get_result(self.game.turn_number)
                    answer = player.get_answer(self.game.turn_number)
                    turn_results['other_answers'].append(
                        {
                            'rank': rank + 1,
                            'player_name': player.name,
                            'distance': result.distance,
                            'score': result.score,
                            'lat': answer.latitude,
                            'lng': answer.longitude,
                        })

        socketio.emit('end_of_turn', turn_results, room=self.game_id)

        # Then send individual player results
        for rank, player in enumerate(ranked_players):
            result = player.get_result(self.game.turn_number)
            answer = player.get_answer(self.game.turn_number)
            socketio.emit('player_results',
                          {
                              'rank': rank + 1,
                              'total': player_count,
                              'distance': result.distance,
                              'score': result.score,
                              'lat': answer.latitude,
                              'lng': answer.longitude,
                          },
                          room=player.sid)

    def update_leaderboard(self):
        app.logger.debug('Updating leaderboard')

        # Get a sorted list of all the scores
        scores = self.game.get_ranked_scores()
        top_ten = [{'player_name': score['player'].name,
                    'score': score['score']} for score in scores[:10]]

        # Number of players
        total_player = len(scores)

        # Send top ten + player score and rank to each player
        for rank, score in enumerate(scores):
            socketio.emit(
                'leaderboard_update',
                {
                    'top_ten': top_ten,
                    'total_player': total_player,
                    'player_rank': rank,
                    'player_score': score['score'],
                },
                room=score['player'].sid)

    def play_again(self):
        self.lock.acquire()

        if (self.remaining_turns == 0 and not self.game.is_turn_happening):
            self.remaining_turns = self.number_of_turns
            socketio.start_background_task(target=self.run_game)

        self.lock.release()
