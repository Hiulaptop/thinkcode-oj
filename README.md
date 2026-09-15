# ThinkCode OJ

Fork of [VNOJ](https://github.com/VNOI-Admin/OJ) / [DMOJ](https://github.com/DMOJ/online-judge). Live at [oj.thinkcode.vn](https://oj.thinkcode.vn/).

## Features

See [DMOJ's feature list](https://github.com/DMOJ/online-judge#features).

## Installation

Native install follows [VNOJ docs](https://vnoi-admin.github.io/vnoj-docs/#/site/installation). Clone this repo instead of DMOJ or VNOJ.

Production is Docker-only. GitHub Actions builds `ghcr.io/hiulaptop/thinkcode-oj` and deploys over SSH. Details: [CI-CD.md](CI-CD.md). Runtime settings come from env; the image copies `dmoj/local_settings.docker.py.example` to `dmoj/local_settings.py`.

### Notes

- Set `DMOJ_PROBLEM_DATA_ROOT` (Docker default: `/problems`). That directory holds the site's working copies. Production judges pull packages from R2 (`BRIDGED_R2_PROBLEMS=True`); they do not read this tree.
- Leave `ENABLE_FTS = False` unless you configure MySQL full-text search. Background: [VNOI-Admin/OJ#4](https://github.com/VNOI-Admin/OJ/issues/4).
- Point `CACHES` at Redis so site, bridged, celery, and the judge share cache. Keep redis-py on RESP2 (`CONNECTION_POOL_KWARGS: {protocol: 2}`). That pin was required on Redis 5; production now runs Redis 8 and still uses it.
- `python3 manage.py loaddata demo` sets the Sites domain to `localhost:8081`. Edit `judge/fixtures/demo.json` or Django admin → Sites.
- Polygon import needs pandoc ≥ 3.0 on the site image (`Dockerfile` installs 3.10.2).
- Load MariaDB timezone tables or `CONVERT_TZ` returns `NULL` (`USE_TZ=True`, default user tz `Asia/Ho_Chi_Minh`):

      mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql mysql

- Put [testlib.h](https://github.com/MikeMirzayanov/testlib/blob/master/testlib.h) on the **judge** image (`thinkcode-judge-server`), in g++'s include path. Precompile the header if compile times hurt.

## Contributing

flake8 on Python. prettier on JS under `websocket/`. See [contributing.md](contributing.md).
