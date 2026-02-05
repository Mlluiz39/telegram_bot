import os
import uuid
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def run_debug():
    today = datetime.now().date().isoformat()
    print(f"Debug: Checking schedules for {today}...")

    try:
        # 1. Fetch active medications
        print("Debug: Fetching active medications...")
        meds_res = supabase.table("medications").select("*").eq("active", True).execute()
        meds = meds_res.data or []
        print(f"Debug: Found {len(meds)} active medications.")

        if not meds:
            return

        for med in meds:
            print(f"Debug: Processing med: {med['name']} (ID: {med['id']})")
            
            # 2. Check history
            print("Debug: Checking existing history...")
            history_res = supabase.table("medication_history") \
                .select("*") \
                .eq("medication_id", med["id"]) \
                .eq("date", today) \
                .execute()
            
            if history_res.data:
                print(f"Debug: History already exists for {med['name']}: {len(history_res.data)} entries.")
                continue
            else:
                print(f"Debug: No history found for {med['name']} today. Generating...")

            # 3. Prepare inserts
            new_records = []
            times = med.get("times", [])
            minutes = med.get("times_minutes", [])
            
            print(f"Debug: Times in DB: {times}")
            print(f"Debug: Minutes in DB: {minutes}")

            if not times:
                print("Debug: No 'times' array found/empty.")
            
            for t_str, t_min in zip(times, minutes):
                uid = str(uuid.uuid4())
                record = {
                    "unique_id": uid,
                    "short_id": uid[:8],
                    "medication_id": med["id"],
                    "patient_id": med["patient_id"],
                    "date": today,
                    "scheduled_time": t_str,
                    "scheduled_minutes": t_min,
                    "status": "pending"
                }
                new_records.append(record)
                print(f"Debug: Prepared record for {t_str} ({t_min} min)")

            if new_records:
                print(f"Debug: Inserting {len(new_records)} records...")
                res = supabase.table("medication_history").insert(new_records).execute()
                print("Debug: Insert success!", res.data)
            else:
                print("Debug: No records prepared (lists might be empty or zipped to 0 length).")

    except Exception as e:
        print(f"Debug Error: {e}")

if __name__ == "__main__":
    run_debug()
