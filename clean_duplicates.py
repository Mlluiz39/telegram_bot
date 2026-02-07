import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def clean_duplicates():
    today = datetime.now().date().isoformat()
    print(f"Cleaning duplicates for: {today}\n")

    try:
        # Fetch all records
        res = supabase.table("medication_history") \
            .select("*") \
            .eq("date", today) \
            .execute()
        
        records = res.data or []
        
        # Group by unique key (medication_id + scheduled_time)
        seen = {} # key -> list of records
        
        for r in records:
            key = (r['medication_id'], r['scheduled_time'])
            if key not in seen:
                seen[key] = []
            seen[key].append(r)
        
        deleted_count = 0
        
        for key, duplicate_list in seen.items():
            if len(duplicate_list) > 1:
                # Keep the one that is 'sent' or 'taken'/'missed' if possible, otherwise just the first one
                # Sort by status priority: taken/missed > sent > pending
                def status_priority(rec):
                    s = rec['status']
                    if s in ['taken', 'missed']: return 3
                    if s == 'sent': return 2
                    return 1
                
                duplicate_list.sort(key=status_priority, reverse=True)
                
                # Keep the first one (highest priority)
                keep = duplicate_list[0]
                to_delete = duplicate_list[1:]
                
                print(f"Keeping {keep['id']} ({keep['status']}) for {key}")
                
                for d in to_delete:
                    print(f"Deleting duplicate {d['id']} ({d['status']})")
                    supabase.table("medication_history").delete().eq("id", d["id"]).execute()
                    deleted_count += 1

        print(f"\nCleanup complete. Deleted {deleted_count} duplicates.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    clean_duplicates()
