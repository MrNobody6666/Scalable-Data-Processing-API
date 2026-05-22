import urllib.request
import json
import time
import threading

API_URL = "http://localhost:8000/trigger-join"
NUM_REQUESTS = 5

def trigger_job(worker_id):
    print(f"[Worker {worker_id}] Triggering join...")
    start_time = time.time()
    try:
        req = urllib.request.Request(API_URL, method='POST', data=b'')
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        job_id = data['job_id']
        print(f"[Worker {worker_id}] Job queued: {job_id}")
        
        # Poll for completion
        while True:
            time.sleep(2)
            status_req = urllib.request.urlopen(f"http://localhost:8000/status/{job_id}")
            status_data = json.loads(status_req.read())
            if status_data['status'] in ['completed', 'failed']:
                end_time = time.time()
                print(f"[Worker {worker_id}] Job {job_id} finished with status '{status_data['status']}' in {end_time - start_time:.2f}s")
                if status_data['status'] == 'failed':
                    print(f"[Worker {worker_id}] Error: {status_data.get('error')}")
                break
    except Exception as e:
        print(f"[Worker {worker_id}] Request failed: {e}")

threads = []
print(f"--- Starting Concurrency Stress Test ({NUM_REQUESTS} concurrent requests) ---")
for i in range(NUM_REQUESTS):
    t = threading.Thread(target=trigger_job, args=(i+1,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("--- Stress Test Completed ---")
