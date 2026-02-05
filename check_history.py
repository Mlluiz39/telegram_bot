import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def check_history():
    today = datetime.now().date().isoformat()
    print(f"Checking history for {today}...")

    try:
        res = supabase.table("medication_history") \
            .select("*") \
            .eq("date", today) \
            .execute()
        
        if not res.data:
            print("No history found for today.")
        else:
            print(f"Found {len(res.data)} entries for today:")
            for item in res.data:
                print(f"- Time: {item['scheduled_time']} (Min: {item['scheduled_minutes']}) | Status: {item['status']} | Med ID: {item['medication_id']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_history()
