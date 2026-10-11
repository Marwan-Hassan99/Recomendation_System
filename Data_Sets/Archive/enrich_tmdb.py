"""
Optional: fill movies.poster_url and stars.home_land / date_of_birth from the TMDB API.
(UNTESTED from my side: the build environment had no access to api.themoviedb.org.)

1) Free API key: https://www.themoviedb.org/settings/api
2) export TMDB_API_KEY=xxxx
3) python enrich_tmdb.py        -> writes data/enrich.sql  (resumable, cached in .tmdb_cache.json)
4) psql -d yourdb -f data/enrich.sql
"""
import json, os, time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

KEY = os.environ["TMDB_API_KEY"]
CACHE_FILE = ".tmdb_cache.json"
cache = json.load(open(CACHE_FILE)) if os.path.exists(CACHE_FILE) else {}
sess = requests.Session()


def get(path):
    if path in cache:
        return cache[path]
    for _ in range(4):
        r = sess.get(f"https://api.themoviedb.org/3{path}", params={"api_key": KEY}, timeout=20)
        if r.status_code == 429:
            time.sleep(2); continue
        cache[path] = r.json() if r.ok else {}
        return cache[path]
    return {}


def q(s):
    return "NULL" if not s else "'" + str(s).replace("'", "''") + "'"


movies = pd.read_csv("extras/movie_external_ids.csv", usecols=["movie_id", "tmdb_id"]).rename(columns={"movie_id": "id"})
stars = pd.read_csv("data/actors.csv", usecols=["id"])

with ThreadPoolExecutor(8) as ex:
    mres = list(ex.map(lambda t: get(f"/movie/{int(t)}"), movies["tmdb_id"]))
    sres = list(ex.map(lambda i: get(f"/person/{int(i)}"), stars["id"]))
json.dump(cache, open(CACHE_FILE, "w"))

with open("data/enrich.sql", "w", encoding="utf-8") as f:
    f.write("BEGIN;\n")
    for mid, r in zip(movies["id"], mres):
        if r.get("poster_path"):
            f.write(f"UPDATE movies SET poster_url={q('https://image.tmdb.org/t/p/w500' + r['poster_path'])} WHERE id={mid};\n")
    for sid, r in zip(stars["id"], sres):
        if r.get("birthday") or r.get("place_of_birth"):
            bd = q(r.get("birthday"))
            f.write(f"UPDATE actors SET home_land={q(r.get('place_of_birth'))}, date_of_birth={bd}::date WHERE id={sid};\n")
    f.write("COMMIT;\n")
print("wrote data/enrich.sql")
