# Message types client -> server
JOIN = "join"      # player enters a map (also used on initial connect)
MOVE = "move"      # player started moving one tile

# Message types server -> client
SNAPSHOT = "snapshot"         # full list of players on the new map
PLAYER_JOINED = "player_joined"
PLAYER_LEFT = "player_left"
PLAYER_MOVED = "player_moved"
