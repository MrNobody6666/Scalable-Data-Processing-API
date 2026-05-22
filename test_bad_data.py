import os
import shutil
import urllib.request
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_CSV = os.path.join(BASE_DIR, "users.csv")
USERS_BAK = os.path.join(BASE_DIR, "users.csv.bak")
API_URL = "http://localhost:8000/trigger-join"

def setup_bad_data():
    print("--- Setting up bad data ---")
    if os.path.exists(USERS_CSV):
        shutil.move(USERS_CSV, USERS_BAK)
    
    # Create a malformed users.csv
    with open(USERS_CSV, "w", encoding="utf-8") as f:
        f.write("user_id,name,email,age,city\n")
        f.write("1,John Doe,john@test.com,25\n") # Missing a column!
        f.write("bad_id_string,Jane Doe,jane@test.com,30,NY\n") # String instead of int ID
        f.write(",,,\n") # Empty row

def restore_good_data():
    print("--- Restoring good data ---")
    if os.path.exists(USERS_BAK):
        shutil.move(USERS_BAK, USERS_CSV)

def run_test():
    try:
        setup_bad_data()
        print("Triggering join with malformed data...")
        req = urllib.request.Request(API_URL, method='POST', data=b'')
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        job_id = data['job_id']
        print(f"Job queued: {job_id}")
        
        while True:
            time.sleep(2)
            status_req = urllib.request.urlopen(f"http://localhost:8000/status/{job_id}")
            status_data = json.loads(status_req.read())
            if status_data['status'] in ['completed', 'failed']:
                print(f"Job {job_id} finished with status '{status_data['status']}'")
                if status_data['status'] == 'failed':
                    print(f"Error captured by API: {status_data.get('error')}")
                break
    finally:
        restore_good_data()

if __name__ == "__main__":
    run_test()
