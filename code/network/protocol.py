# Message types client -> server
JOIN = "join"                # player enters a map; includes spawn_zones list
MOVE = "move"                # player moved one tile
TURN = "turn"                # player changed direction without moving
POKEMON_ENCOUNTER = "pokemon_encounter"  # player's hitbox touched a wild Pokémon

# Message types server -> client
SNAPSHOT         = "snapshot"           # full list of players already on the map
PLAYER_JOINED    = "player_joined"
PLAYER_LEFT      = "player_left"
PLAYER_MOVED     = "player_moved"
PLAYER_TURNED    = "player_turned"      # player changed direction without moving

POKEMON_SNAPSHOT       = "pokemon_snapshot"        # wild Pokémon already on the map (on join)
POKEMON_SPAWNED        = "pokemon_spawned"          # new wild Pokémon appeared
POKEMON_MOVED          = "pokemon_moved"            # wild Pokémon moved one tile
POKEMON_DESPAWNED      = "pokemon_despawned"        # wild Pokémon removed
POKEMON_ENCOUNTER_START = "pokemon_encounter_start" # server confirms encounter (for battle)
