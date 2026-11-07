# Isolated Python 3.14 verification

Run from the repository root. These tests create and delete disposable MySQL
schemas. Never point them at a shared database. The Compose network is internal,
with no published ports, Docker socket, production credentials, or host data mounts.
The database uses latin1 because the legacy AntibodyHistory primary key exceeds
MySQL's index limit with utf8mb4. Production schema definitions are unchanged.

```sh
docker build -f flaskcelery.Dockerfile -t lightserv-port:app .
docker build -f tests/container/Dockerfile -t lightserv-port:test .
docker compose -p lightserv-port-smoke -f tests/container/compose.yml up -d db redis
docker compose -p lightserv-port-smoke -f tests/container/compose.yml run --rm smoke
docker compose -p lightserv-port-smoke -f tests/container/compose.yml run --rm smoke pytest -q lightserv/tests/test_main.py lightserv/tests/test_requests.py -k 'not successful_spock_connection'
docker compose -p lightserv-port-smoke -f tests/container/compose.yml run --rm -e CELERY_RESULT_BACKEND=db+mysql+pymysql://root:isolated-only@db/port_celery smoke python -m container_tests.worker
docker compose -p lightserv-port-smoke -f tests/container/compose.yml down -v
```

Run the database tests sequentially: legacy fixtures drop their test schemas at
teardown. Concurrent application imports can race to recreate them. The worker
check loads the production schedule without dispatching its jobs, then publishes
only `hello` through Redis and checks SQLAlchemy result persistence. The current
production schedule has **12** entries (the draft spec said 11).

## Viewer images

Each variant retains its original build context and launcher command. For example:

```sh
docker build -f viewer-launcher/viewer-launcher.Dockerfile -t lightserv-port:launcher viewer-launcher
docker build -f neuroglancer-docker/neuroglancer/neuroglancer.Dockerfile -t lightserv-port:neuroglancer neuroglancer-docker/neuroglancer
docker build -f cloudvolume-docker/cloudvolume.Dockerfile -t lightserv-port:cloudvolume cloudvolume-docker
```

The ten Neuroglancer directories contain identical resolved requirements so their
existing independent build commands keep working. Refresh them together from
`neuroglancer-docker/requirements.in`. Viewer-launcher has its own requirements.in.
The app uses `uv.lock`; regenerate requirements.txt with
`uv export --frozen --no-dev --no-hashes --output-file requirements.txt`.

`launcher.py` checks the HTTP/Docker request contract with the Docker client
mocked; mount it at `/app/smoke_launcher.py` in the launcher image and run with
`FLASK_MODE=TEST`, `--network none`, and `python smoke_launcher.py`.

`http.py` expects a volume service named `lightserv-port-volume` on port 1337,
with JSON `info`, raw `chunk` containing `0123456789`, and `compressed.gz`
containing the gzip encoding of those bytes. It checks GET/HEAD/OPTIONS, gzip,
ranges, missing paths, and rejected writes. Use only a synthetic read-only mount.

## Verified in this port

- App, viewer-launcher, nginx volume server, and all ten Neuroglancer images built.
- All ten viewer launchers stayed running and wrote their viewer records to Redis
  with appropriate synthetic session fields. Raw expects channel/lightsheet names;
  registration expects `cvs_need_atlas`; fiber expects image and Paxinos layers.
- App smoke: exact DataJoint version, 12 production/1 development schedule entries,
  timezone, task registration, login/audit database writes, pages/table, eager task.
- Main/request suite: 44 passed, 1 deselected (external SSH integration).
- Real Celery worker and beat publication through Redis, SQL result persistence.
- Gunicorn and Flower HTTP 200; beat CLI startup with empty TEST schedule.
- Launcher request contract and static-volume HTTP checks passed.

Released cloud-volume 12.15.2 and pysimdjson 7.0.2 install and import on Python
3.14 when build-essential is installed. A slim image without a compiler fails on
posix_ipc. No pysimdjson/orjson patch is needed or included. The spec's nginx image
serves the volume directly and therefore needs neither package.

## Production validation still required

This is an isolated compatibility result, not deployment approval or a full legacy
baseline comparison. The rest of the imaging/clearing/processing suite and actual
scheduled pipeline jobs have not been exercised against production-like datasets.

- Confirm actual production schemas, grants, TLS, timezone, and legacy-vs-new
  cascade-delete behavior on a disposable copy; no production DB was contacted.
- Verify authentication headers/hostname and `/cv/` proxy rewriting, including
  Range, OPTIONS, and Content-Encoding, through the real front-end proxy.
- Render representative volumes in the hosted BrainCOGS client. Viewer startup
  does not establish browser rendering or interactive ontology-tool compatibility.
- Check `/jukebox` read permissions for nginx uid 101 and real compression formats.
  nginx serves compressed bytes with Content-Encoding and fails startup when
  `/mnt/data/info` is absent; it no longer supplies random fallback data.
- SSH keys are no longer copied into the image. Runtime credential mounting must
  be arranged before pipeline use. Proposed Compose key-mount edits were rejected
  by automatic approval review and were not applied. Existing Compose credentials
  and mounts were otherwise preserved.
- Validate Spock paths/hostname, SMTP, and Calendar credentials. Those integrations
  were not migrated or exercised; existing defaults remain.

No production deployment, production database write, upstream code change, or PR
was performed. The pre-existing modernization spec was preserved.
