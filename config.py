# How long is given to players to answer a question
import os


MAX_RESPONSE_TIME = 8

# Number of seconds between each turns
TIME_BETWEEN_TURNS = 5

# Number of answer used to compute ranking
LEADERBOARD_ANSWER_COUNT = 20

# The distance above which score is zero
SCORE_MAX_DISTANCE = 2000

# Allow players to answer multiple times to the same question
ALLOW_MULTIPLE_ANSWER = 1  # 0 for False, 1 for True

# How many zoom level are allowed (max 2)
ZOOM_LEVEL = 0

# CDN URL
CDN_URL = 'static'

# List of origins that are allowed to connect to this server.
CORS_ALLOWED_ORIGINS = '*'

# Host and port the server should listen.
HOST='0.0.0.0'
PORT=int(os.environ.get('PORT', 8000))
