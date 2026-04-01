import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# PostgreSQL connection string from environment variables
engine = create_engine(os.getenv("DB_URL"))

# PostgreSQL connection string
#engine = create_engine("postgresql://postgres:NFarCNHhYpAuesiKCCkkguTWFIyiKqIQ@interchange.proxy.rlwy.net:22483/railway", pool_pre_ping=True)

file_list = [
    "databases/Album.csv", "databases/Artist.csv", "databases/Customer.csv", "databases/Employee.csv", 
    "databases/Genre.csv", "databases/Invoice.csv", "databases/InvoiceLine.csv", "databases/MediaType.csv", 
    "databases/Playlist.csv", "databases/PlaylistTrack.csv", "databases/Track.csv"
]

for file in file_list:
    try:
        temp_df = pd.read_csv(file)

        # Extract table name without folder path
        table_name = os.path.basename(file).split('.')[0]

        temp_df.to_sql(table_name, engine, if_exists="replace", index=False)

        print(f"Successfully uploaded {file} to table '{table_name}'")
        
    except Exception as e:
        print(f"Error uploading {file}: {e}")


print("\n--- Verifying table 'Artist' ---")
with engine.connect() as conn:
    try:
        result = conn.execute(text("SELECT * FROM \"Artist\" LIMIT 5;"))
        for row in result:
            print(row)
    except Exception as e:
        print(f"Could not verify: {e}")