"""
ETL: MovieLens (ml-latest-small) + TMDB 5000 (movies + credits)  ->  CSVs matching schema.sql

Inputs  (./raw):  ratings.csv movies.csv links.csv tmdb_5000_movies.csv tmdb_5000_credits.csv
Outputs (./data):   the 6 backend tables as CSV (+ full_dump.sql).  (./extras): optional files outside the backend schema
                  + full_dump.sql  (schema + data, load with:  psql -d yourdb -f full_dump.sql)

Run:  pip install pandas faker bcrypt && python etl.py
"""
import json
import os
import random

import bcrypt
import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
RAW, OUT = "raw", "data"
MIN_USER_RATINGS = 5
random.seed(SEED)
np.random.seed(SEED)
EXTRA = "extras"
os.makedirs(OUT, exist_ok=True)
os.makedirs(EXTRA, exist_ok=True)

# ----------------------------------------------------------------------------- load
ratings = pd.read_csv(f"{RAW}/ratings.csv")
links = pd.read_csv(f"{RAW}/links.csv").dropna(subset=["tmdbId"])
links["tmdbId"] = links["tmdbId"].astype(int)
links = links.drop_duplicates("tmdbId")
tmdb = pd.read_csv(f"{RAW}/tmdb_5000_movies.csv")
credits = pd.read_csv(f"{RAW}/tmdb_5000_credits.csv").rename(columns={"movie_id": "id"})

# ----------------------------------------------------------------------------- movies
df = links.merge(tmdb, left_on="tmdbId", right_on="id", how="inner")
df = df.merge(credits[["id", "cast", "crew"]], on="id", how="left")
df = df[df["movieId"].isin(ratings["movieId"])]            # keep movies that have ratings


def producer(crew_json):
    try:
        for p in json.loads(crew_json):
            if p.get("job") == "Producer":
                return p["name"]
    except Exception:
        pass
    return None


def first_genre(g):
    g = json.loads(g)
    return g[0]["name"] if g else None



movies = pd.DataFrame({
    "id": df["movieId"],
    "title": df["title"],
    "story_line": df["overview"],
    "producer_name": df["crew"].map(producer),
    "category": df["genres"].map(first_genre),
    "release_date": pd.to_datetime(df["release_date"], errors="coerce").dt.date,
    "poster_url": None,                                       # not in these sources, see README
    "status": df["status"].map(lambda x: "released" if x == "Released" else "upcoming"),
    "imdb_rating": df["vote_average"].where(df["vote_count"] > 0).round(1),
    "internal_rating": np.nan,                                # filled below
    "tmdb_id": df["tmdbId"],
    "imdb_id": "tt" + df["imdbId"].astype(int).astype(str).str.zfill(7),
}).drop_duplicates("id")
# backend schema has UNIQUE(title): keep, per duplicated title, the movie with the most ratings
movies["_n"] = movies["id"].map(ratings["movieId"].value_counts()).fillna(0)
movies = movies.sort_values("_n", ascending=False).drop_duplicates("title").drop(columns="_n")
movies = movies.sort_values("id").reset_index(drop=True)
valid_movies = set(movies["id"])

# ----------------------------------------------------------------------------- genres / stars
genres_rows, mg_rows, stars_rows, ms_rows = [], [], [], []
for _, r in df[df["movieId"].isin(valid_movies)].iterrows():
    for g in json.loads(r["genres"]):
        genres_rows.append((g["id"], g["name"]))
        mg_rows.append((r["movieId"], g["id"]))
    try:
        for c in json.loads(r["cast"])[:5]:                   # top-5 billed actors
            stars_rows.append((c["id"], c["name"]))
            ms_rows.append((r["movieId"], c["id"]))
    except Exception:
        pass

genres = pd.DataFrame(genres_rows, columns=["id", "name"]).drop_duplicates("id")
movie_genres = pd.DataFrame(mg_rows, columns=["movie_id", "genre_id"]).drop_duplicates()
stars = pd.DataFrame(stars_rows, columns=["id", "name"]).drop_duplicates("id")
stars["home_land"] = None
stars["date_of_birth"] = None
stars["role"] = "star"
movie_actors = pd.DataFrame(ms_rows, columns=["movie_id", "actor_id"]).drop_duplicates()

# ----------------------------------------------------------------------------- reviews
rv = ratings[ratings["movieId"].isin(valid_movies)].copy()
cnt = rv.groupby("userId")["movieId"].transform("count")
rv = rv[cnt >= MIN_USER_RATINGS].sort_values("timestamp").reset_index(drop=True)
rv["created_at"] = pd.to_datetime(rv["timestamp"], unit="s", utc=True)
reviews = pd.DataFrame({
    "id": np.arange(1, len(rv) + 1),
    "review": None,                                           # MovieLens has no review text
    "rating": (rv["rating"] * 2).round(1),                    # 0.5-5  ->  1-10
    "user_id": rv["userId"],
    "movie_id": rv["movieId"],
    "created_at": rv["created_at"],
    "updated_at": rv["created_at"],
})

# internal_rating = AVG(reviews.rating)
avg = reviews.groupby("movie_id")["rating"].mean().round(1)
movies["internal_rating"] = movies["id"].map(avg)

# ----------------------------------------------------------------------------- users
fake = Faker()
Faker.seed(SEED)
pw = bcrypt.hashpw(b"password123", bcrypt.gensalt(rounds=10)).decode()   # same demo password for all
first_ts = rv.groupby("userId")["created_at"].min()
uids = sorted(first_ts.index)
users = pd.DataFrame({
    "id": uids,
    "full_name": [fake.name() for _ in uids],
    "hashed_password": pw,
    "created_at": [first_ts[u] - pd.Timedelta(days=random.randint(0, 30)) for u in uids],
})
users["email"] = [f"user{u}@example.com" for u in users["id"]]
users["updated_at"] = users["created_at"]
users["role"] = "user"
users.loc[users["id"] == users["id"].min(), "role"] = "admin"
users = users[["id", "email", "hashed_password", "full_name", "created_at", "updated_at", "role"]]

# ----------------------------------------------------------------------------- watch_list (derived)
wl = rv.rename(columns={"userId": "user_id", "movieId": "movie_id"})[
    ["user_id", "movie_id", "rating", "created_at"]].copy()
wl["watch_status"] = np.where(wl["rating"] <= 1.0, "dropped", "watched")
wl = wl.rename(columns={"created_at": "set_at"})[["movie_id", "user_id", "watch_status", "set_at"]]

# plan_to_watch / watching: sampled from popular movies the user has NOT rated
pop = reviews["movie_id"].value_counts()
top_movies = pop.head(1000)
weights = (top_movies / top_movies.sum()).values
rated = reviews.groupby("user_id")["movie_id"].apply(set).to_dict()
last_ts = rv.groupby("userId")["created_at"].max()
extra = []
for u in uids:
    cand = [m for m in top_movies.index if m not in rated[u]]
    w = np.array([weights[list(top_movies.index).index(m)] for m in cand])
    pick = np.random.choice(cand, size=min(7, len(cand)), replace=False, p=w / w.sum())
    for i, m in enumerate(pick):
        status = "watching" if i < 2 else "plan_to_watch"
        ts = last_ts[u] + pd.Timedelta(days=random.randint(1, 60))
        extra.append((int(m), u, status, ts))
wl = pd.concat([wl, pd.DataFrame(extra, columns=wl.columns)], ignore_index=True)
# backend enum is only (watched, listed)
wl["watch_status"] = wl["watch_status"].replace(
    {"plan_to_watch": "listed", "watching": "listed", "dropped": "watched"})
wl["updated_at"] = wl["set_at"]

# ----------------------------------------------------------------------------- write
core = {
    "users": users,
    "movies": movies.drop(columns=["tmdb_id", "imdb_id"]),
    "actors": stars[["id", "role", "name", "home_land", "date_of_birth"]],
    "movie_actors": movie_actors,
    "reviews": reviews,
    "watch_list": wl,
}
extras = {   # NOT part of the backend schema: kept separately
    "genres": genres,
    "movie_genres": movie_genres,
    "movie_external_ids": movies[["id", "tmdb_id", "imdb_id"]].rename(columns={"id": "movie_id"}),
}
for folder, group in ((OUT, core), (EXTRA, extras)):
    for name, t in group.items():
        t = t.astype(object).where(t.notna(), None)
        t.to_csv(f"{folder}/{name}.csv", index=False)
        print(f"{folder}/{name:20s} {len(t):>8,d} rows")

# ----------------------------------------------------------------------------- full_dump.sql
order = ["users", "movies", "actors", "movie_actors", "reviews", "watch_list"]
with open(f"{OUT}/full_dump.sql", "w", encoding="utf-8") as out:
    out.write(open("schema.sql", encoding="utf-8").read() + "\n")
    for name in order:
        cols = ",".join(pd.read_csv(f"{OUT}/{name}.csv", nrows=0).columns)
        out.write(f"COPY {name} ({cols}) FROM stdin WITH (FORMAT csv, HEADER true);\n")
        with open(f"{OUT}/{name}.csv", encoding="utf-8") as f:
            out.write(f.read())
        out.write("\\.\n\n")
    for name in ["users", "movies", "actors", "reviews"]:
        out.write(f"SELECT setval(pg_get_serial_sequence('{name}','id'), (SELECT MAX(id) FROM {name}));\n")
    out.write("ANALYZE;\n")
print("wrote", f"{OUT}/full_dump.sql")
