mongodb-tool-install:
    sudo apt-get install gnupg curl
    curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | \
    sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg \
    --dearmor
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
    sudo apt-get update
    sudo apt install mongodb-database-tools

redis-tool-install:
    sudo apt-get install lsb-release curl gpg
    curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
    sudo chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
    sudo apt-get update
    sudo apt install redis-tools # for redis-cli

import-data:
    mongoimport --db mcim_backend --collection modrinth_projects --file ./data/modrinth_projects.json --jsonArray
    mongoimport --db mcim_backend --collection modrinth_versions --file ./data/modrinth_versions.json --jsonArray
    mongoimport --db mcim_backend --collection modrinth_files --file ./data/modrinth_files.json --jsonArray
    mongoimport --db mcim_backend --collection modrinth_loaders --file ./data/modrinth_loaders.json --jsonArray
    mongoimport --db mcim_backend --collection modrinth_game_versions --file ./data/modrinth_game_versions.json --jsonArray
    mongoimport --db mcim_backend --collection modrinth_categories --file ./data/modrinth_categories.json --jsonArray
    mongoimport --db mcim_backend --collection curseforge_mods --file ./data/curseforge_mods.json --jsonArray
    mongoimport --db mcim_backend --collection curseforge_files --file ./data/curseforge_files.json --jsonArray
    # mongoimport --db mcim_backend --collection curseforge_fingerprint --file ./data/curseforge_fingerprints.json --jsonArray
    mongoimport --db mcim_backend --collection curseforge_categories --file ./data/curseforge_categories.json --jsonArray

    redis-cli --pipe < ./data/redis_data.txt

ci-install:
    pip install -r requirements.txt
    pip install pytest

ci-test:
    pytest ./tests -vv -rpP

ci-config:
    echo $CONFIG > config.json