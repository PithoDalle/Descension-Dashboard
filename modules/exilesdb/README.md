# ExilesDB module (optional)

Shows an offline copy of db.exil.es (the Ascension item/spell/quest/NPC database) as a tab in the dashboard.

- **Not included:** the archive itself, about 13 GB. This folder contains only the code.
- **Enable:** put the archive somewhere (it must contain `data/mirror.sqlite`, `data/offline_site.sqlite` and `mirror/`), then set *ExilesDB data folder* in Settings. The tab appears and starts the archive server on first open.
- **Disable / remove:** delete this `modules/exilesdb` folder. The tab and the Settings fields disappear and nothing else is affected.
- The server runs on `127.0.0.1` only, port 8081 by default (*ExilesDB port* in Settings). It stops when the dashboard closes.
- Log: `exilesdb.log` in this folder.
