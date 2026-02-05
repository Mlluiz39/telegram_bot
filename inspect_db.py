import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

try:
    print("Fetching medications...")
    res = supabase.table("medications").select("*").limit(1).execute()
    if res.data:
        print("Medications Sample:", res.data[0])
    else:
        print("Medications table is empty.")

    print("\nFetching medication_history...")
    res2 = supabase.table("medication_history").select("*").limit(1).execute()
    if res2.data:
        print("History Sample:", res2.data[0])
    else:
        print("History table is empty.")

except Exception as e:
    print(f"Error: {e}")
