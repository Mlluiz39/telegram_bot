import os
import asyncio
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
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    print(f"Current Server Time: {now} (Minutes: {current_minutes})")
    print(f"Checking history for: {today}\n")

    try:
        res = supabase.table("medication_history") \
            .select("*, medications(name, dosage)") \
            .eq("date", today) \
            .execute()
        
        records = res.data or []
        records.sort(key=lambda x: x['scheduled_minutes'])

        print(f"{'Time':<10} | {'Minutes':<8} | {'Status':<10} | {'Medication':<20} | {'Expected Min'}")
        print("-" * 80)
        
        for r in records:
            time_str = r['scheduled_time']
            sch_min = r['scheduled_minutes']
            status = r['status']
            med_name = r['medications']['name']
            
            # Calculate expected minutes from time string to check consistency
            h, m = map(int, time_str.split(':'))
            expected_min = h * 60 + m
            
            flag = ""
            if sch_min != expected_min:
                flag = f"MISMATCH! ({expected_min})"
            elif sch_min <= current_minutes and status == 'pending':
                flag = "SHOULD HAVE SENT?"

            print(f"{time_str:<10} | {sch_min:<8} | {status:<10} | {med_name:<20} | {flag}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_history()
