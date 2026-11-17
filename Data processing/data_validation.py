import pandas as pd

data_path = "Data_Sets/data/"

movies = pd.read_csv(data_path + "movies.csv")
actors = pd.read_csv(data_path + "actors.csv")
movie_actors = pd.read_csv(data_path + "movie_actors.csv")
reviews = pd.read_csv(data_path + "reviews.csv")
users = pd.read_csv(data_path + "users.csv")
watch_list = pd.read_csv(data_path + "watch_list.csv")

# check pk , fk 

foreign_keys = {
    "reviews -> users": (reviews, "user_id", users, "id"),
    "reviews -> movies": (reviews, "movie_id", movies, "id"),

    "watch_list -> users": (watch_list, "user_id", users, "id"),
    "watch_list -> movies": (watch_list, "movie_id", movies, "id"),

    "movie_actors -> movies": (
        movie_actors, "movie_id", movies, "id"
    ),

    "movie_actors -> actors": (
        movie_actors, "actor_id", actors, "id"
    )
}

for relation, (child_df, fk, parent_df, pk) in foreign_keys.items():

    invalid = ~child_df[fk].isin(parent_df[pk])

    print(f"\n{relation}")
    print("Invalid References:", invalid.sum())

