import os
from datetime import datetime
from collections import Counter
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def check_duplicates():
    today = datetime.now().date().isoformat()
    print(f"Checking for duplicates on: {today}\n")

    try:
        res = supabase.table("medication_history") \
            .select("*, medications(name)") \
            .eq("date", today) \
            .execute()
        
        records = res.data or []
        
        # Check for duplicates based on medication_id and scheduled_time
        seen = []
        duplicates = []
        
        for r in records:
            key = (r['medication_id'], r['scheduled_time'])
            if key in seen:
                duplicates.append(r)
            else:
                seen.append(key)
        
        if duplicates:
            print(f"FOUND {len(duplicates)} DUPLICATE RECORDS:")
            for d in duplicates:
                print(f"- {d['medications']['name']} at {d['scheduled_time']} (ID: {d['id']}, Status: {d['status']})")
        else:
            print("No duplicate records found in database.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_duplicates()
