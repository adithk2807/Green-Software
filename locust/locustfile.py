"""
Locust workload — mixed static file requests simulating real web traffic.
Small HTML files are most frequent (5x), medium JSON moderate (3x),
large binary least frequent (2x).
"""
from locust import HttpUser, task, between

class NginxUser(HttpUser):
    wait_time = between(0.5, 2)   # realistic user pacing

    @task(5)
    def get_small(self):
        self.client.get("/small.html", name="small_html_2KB")

    @task(3)
    def get_medium(self):
        self.client.get("/medium.json", name="medium_json_20KB")

    @task(2)
    def get_large(self):
        self.client.get("/large.bin", name="large_bin_200KB")