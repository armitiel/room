# Backend i orkiestracja
Plan: Python, lekki interfejs HTTP i pojedynczy worker.
Moduły: ingest, extraction, validation, scene_jobs, sessions.
Sekrety tylko w środowisku serwera. Wyniki AI wymagają walidacji i zatwierdzenia operatora.
Kontrakty endpointów opisuje docs/architecture.md. Żaden endpoint nie jest jeszcze uruchomiony.