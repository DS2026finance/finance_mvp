import pandas as pd
import sqlite3

# Load the CSV
df = pd.read_csv("sales_sample.csv")

# Add Year and Quarter columns for easier SQL queries
df["Year"] = pd.to_datetime(df["Month"]).dt.year
df["Quarter"] = pd.to_datetime(df["Month"]).dt.quarter

# Create SQLite database
conn = sqlite3.connect("sales.db")
df.to_sql("sales_data", conn, if_exists="replace", index=False)

print("Database created successfully: sales.db")