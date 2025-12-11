.DEFAULT_GOAL := help
SHELL := bash

.PHONY : docker help up down

up:
	docker compose -f ./docker-compose.yaml up -d

down:
	docker compose -f ./docker-compose.yaml down
	
import-db:
	sudo docker cp ./DB/CloudRagDB.sql sqlpreview:/tmp/CloudRagDB.sql
	sudo docker exec -it sqlpreview /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P Im@5ldnm! -i /tmp/CloudRagDB.sql


# Show this help prompt.
help:
	@ echo 'Helpers for development inside fisbu based on fastapi using fastapi-serviceutils.'
	@ echo
	@ echo '  Usage:'
	@ echo ''
	@ echo '    make <target> [flags...]'
	@ echo ''
	@ echo '  Targets:'
	@ echo ''
	@ awk '/^#/{ comment = substr($$0,3) } comment && /^[a-zA-Z][a-zA-Z0-9_-]+ ?:/{ print "   ", $$1, comment }' $(MAKEFILE_LIST) | column -t -s ':' | sort
	@ echo ''
	@ echo '  Flags:'
	@ echo ''
	@ awk '/^#/{ comment = substr($$0,3) } comment && /^[a-zA-Z][a-zA-Z0-9_-]+ ?\?=/{ print "   ", $$1, $$2, comment }' $(MAKEFILE_LIST) | column -t -s '?=' | sort
