# Movie Recommendation DB v3: matches the latest backend schema

## Quick start (PostgreSQL, tested on 16)
```bash
createdb movies
psql -d movies -f data/full_dump.sql          # backend schema + data
psql -d movies -f optional_improvements.sql   # OPTIONAL (genres, tmdb/imdb ids, extra indexes), run from this folder
```

## Folders
- `data/`: the 6 backend tables as CSV + `full_dump.sql` (schema + data)
- `extras/`: data that is NOT in the backend schema (genres, movie_genres, movie_external_ids), only used by `optional_improvements.sql`
- `schema.sql`: the backend schema | `etl.py` + `raw/`: reproduce everything | `enrich_tmdb.py`: optional TMDB fill-in

## schema.sql vs what the backend sent
Exactly as sent, except:
1. Syntax fix: `CREATE TYPE "actor_role" AS ENUM ('star',)` had a trailing comma and no `;`.
2. Typo fix: `movie_actors.actor_id REFERENCES actor(id)` -> `actors(id)`.
3. NOT NULL removed (agreed with the backend, data not available): `movies.poster_url`, `movies.producer_name`, `actors.home_land`, `actors.date_of_birth`.

## Contents
| table | rows | notes |
|---|---|---|
| users | 610 | MovieLens userIds; names via Faker; `userN@example.com`; password for all = `password123` (bcrypt); user 1 = admin |
| movies | 3,533 | MovieLens ids + TMDB 5000 metadata; `status` = released; `imdb_rating` = TMDB vote_average; `internal_rating` = AVG(reviews.rating) |
| actors | 6,563 | TMDB top-5 billed cast per movie; `id` = TMDB person id; `role` = star |
| movie_actors | 17,596 | |
| reviews | 70,184 | MovieLens ratings x2 (1-10), real timestamps in `created_at` (= `updated_at`), `review` text is NULL |
| watch_list | 74,454 | DERIVED (see below) |

Enum mapping for `watch_list.watch_status` (backend has only watched/listed):
rated movies -> `watched` (70,184, including low ratings that were "dropped"); sampled unrated popular movies -> `listed` (4,270).

## Limitations
- Only movies in BOTH MovieLens and TMDB-5000 are kept (3,533 of 9,742). Duplicate titles dropped (UNIQUE(title)). Users with < 5 ratings dropped. Rating density about 3.3%.
- NULL on purpose: `poster_url` (all), `actors.home_land` / `date_of_birth` (all), `producer_name` (440 movies), `reviews.review` (MovieLens has no text).
  `enrich_tmdb.py` (free TMDB key, untested from my side) generates `data/enrich.sql` for posters/birth data.
- `imdb_rating` is TMDB's vote_average, not scraped from IMDb. `imdb_id` is in `extras/` if you want to join the official IMDb ratings.
- `watch_list` and `users` are synthetic/derived: fine for training, not real user data.

## Train/test tip
`reviews.created_at` now exists, so split by time per user (last 20% of each user's reviews = test).
Do NOT use `movies.internal_rating` as a feature (computed from all reviews, including test).

## Re-run
`pip install pandas faker bcrypt && python etl.py`
Sources: MovieLens ml-latest-small (non-commercial, cite Harper & Konstan 2015); TMDB 5000 dataset (attribution required).
