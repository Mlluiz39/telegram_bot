import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def fix_schedule_data():
    today = datetime.now().date().isoformat()
    print(f"Checking and fixing schedule data for: {today}\n")

    try:
        # Fetch all records for today
        res = supabase.table("medication_history") \
            .select("*") \
            .eq("date", today) \
            .execute()
        
        records = res.data or []
        
        updates_count = 0
        
        for r in records:
            time_str = r['scheduled_time']
            current_min = r['scheduled_minutes']
            
            # Calculate correct minutes
            try:
                h, m = map(int, time_str.split(':'))
                correct_min = h * 60 + m
            except ValueError:
                print(f"Skipping invalid time format: {time_str}")
                continue

            if current_min != correct_min:
                print(f"Fixing ID {r['id']} ({time_str}): {current_min} -> {correct_min}")
                
                # Update the record
                supabase.table("medication_history") \
                    .update({"scheduled_minutes": correct_min}) \
                    .eq("id", r["id"]) \
                    .execute()
                
                updates_count += 1
        
        print(f"\nRepair complete. Fixed {updates_count} records.")

    except Exception as e:
        print(f"Error during repair: {e}")

if __name__ == "__main__":
    fix_schedule_data()
