
import pandas as pd 

path = "Data_Sets/data/"


files = [
    "actors.csv",
    "movie_actors.csv",
    "movies.csv",
    "reviews.csv",
    "users.csv",
    "watch_list.csv"
]


for file in files:
    
    df=pd.read_csv(path+file)
    
    print(f"{file} shape= {df.shape}")
    
    print(f"{file} duplicates= {df.duplicated().sum()}")
    
    print(f"{file} info:\n {df.info()}")
    
    print(f"{file} Statistcs: \n {df.describe()}")
    
    print(f"{file} Missing: \n {df.isnull().sum()}")
