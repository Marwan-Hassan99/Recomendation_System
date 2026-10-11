-- OPTIONAL, not part of the backend schema. Apply only if you want them.
-- Run AFTER data/full_dump.sql, from the folder that contains extras/ :
--     psql -d movies -f optional_improvements.sql
\set ON_ERROR_STOP on
BEGIN;

-- 1) genres (many-to-many): useful for content-based recommendation
CREATE TABLE genres (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE movie_genres (
    movie_id INT NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    genre_id INT NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY (movie_id, genre_id)
);
\copy genres FROM 'extras/genres.csv' CSV HEADER
\copy movie_genres FROM 'extras/movie_genres.csv' CSV HEADER
CREATE INDEX idx_movie_genres_genre ON movie_genres(genre_id);

-- 2) external ids on movies (to join IMDb / TMDB data later)
ALTER TABLE movies ADD COLUMN tmdb_id INT UNIQUE, ADD COLUMN imdb_id TEXT UNIQUE;
CREATE TEMP TABLE _ext (movie_id INT, tmdb_id INT, imdb_id TEXT);
\copy _ext FROM 'extras/movie_external_ids.csv' CSV HEADER
UPDATE movies m SET tmdb_id = e.tmdb_id, imdb_id = e.imdb_id FROM _ext e WHERE e.movie_id = m.id;

-- 3) indexes the recommendation queries need (the backend schema has none on reviews)
CREATE INDEX reviews_user_id_idx     ON reviews(user_id);
CREATE INDEX reviews_movie_id_idx    ON reviews(movie_id);
CREATE INDEX reviews_created_at_idx  ON reviews(created_at);
CREATE INDEX movie_actors_actor_idx  ON movie_actors(actor_id);

COMMIT;
