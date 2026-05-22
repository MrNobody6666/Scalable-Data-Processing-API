"""
generate_data.py
================
Generates two large CSV files (~500 MB each) for testing the out-of-core
data join pipeline.

Files produced:
  - users.csv        (~5 million rows)
  - transactions.csv (~8 million rows)

Usage:
    python generate_data.py
"""

import csv
import os
import random
import time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NUM_USERS = 5_000_000
NUM_TRANSACTIONS = 8_000_000
CHUNK_SIZE = 100_000  # rows written per batch

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(OUTPUT_DIR, "users.csv")
TRANSACTIONS_FILE = os.path.join(OUTPUT_DIR, "transactions.csv")

# ---------------------------------------------------------------------------
# Sample data pools
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen", "Daniel",
    "Lisa", "Matthew", "Nancy", "Anthony", "Betty", "Mark", "Margaret",
    "Andrew", "Sandra", "Joshua", "Ashley", "Steven", "Dorothy", "Kevin",
    "Kimberly", "Brian", "Emily", "George", "Donna", "Timothy", "Michelle",
    "Ronald", "Carol", "Edward", "Amanda", "Jason", "Melissa", "Jeffrey",
    "Deborah",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts",
]

CITIES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
    "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
    "Austin", "Jacksonville", "Fort Worth", "Columbus", "Charlotte",
    "Indianapolis", "San Francisco", "Seattle", "Denver", "Nashville",
    "Oklahoma City", "El Paso", "Boston", "Portland", "Las Vegas",
    "Memphis", "Louisville", "Baltimore", "Milwaukee", "Albuquerque",
]

DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "proton.me"]

CATEGORIES = [
    "Electronics", "Groceries", "Clothing", "Entertainment", "Travel",
    "Healthcare", "Education", "Dining", "Utilities", "Insurance",
    "Automotive", "Home Improvement", "Fitness", "Subscriptions", "Gifts",
]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
def _random_email(first: str, last: str, uid: int) -> str:
    """Build a plausible email address."""
    domain = random.choice(DOMAINS)
    return f"{first.lower()}.{last.lower()}{uid}@{domain}"


def generate_users() -> None:
    """Write users.csv in chunks."""
    print(f"Generating {NUM_USERS:,} users -> {USERS_FILE}")
    start = time.perf_counter()

    with open(USERS_FILE, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["user_id", "name", "email", "age", "city"])

        for chunk_start in range(1, NUM_USERS + 1, CHUNK_SIZE):
            rows = []
            for uid in range(chunk_start, min(chunk_start + CHUNK_SIZE, NUM_USERS + 1)):
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                rows.append([
                    uid,
                    f"{first} {last}",
                    _random_email(first, last, uid),
                    random.randint(18, 80),
                    random.choice(CITIES),
                ])
            writer.writerows(rows)

            done = min(chunk_start + CHUNK_SIZE - 1, NUM_USERS)
            if done % 1_000_000 == 0 or done == NUM_USERS:
                elapsed = time.perf_counter() - start
                print(f"  ... {done:>10,} / {NUM_USERS:,}  ({elapsed:.1f}s)")

    size_mb = os.path.getsize(USERS_FILE) / (1024 * 1024)
    print(f"  [OK] users.csv written -- {size_mb:.1f} MB\n")


def generate_transactions() -> None:
    """Write transactions.csv in chunks."""
    print(f"Generating {NUM_TRANSACTIONS:,} transactions -> {TRANSACTIONS_FILE}")
    start = time.perf_counter()

    with open(TRANSACTIONS_FILE, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["transaction_id", "user_id", "amount", "date", "category"])

        for chunk_start in range(1, NUM_TRANSACTIONS + 1, CHUNK_SIZE):
            rows = []
            for tid in range(chunk_start, min(chunk_start + CHUNK_SIZE, NUM_TRANSACTIONS + 1)):
                rows.append([
                    tid,
                    random.randint(1, NUM_USERS),
                    round(random.uniform(1.0, 9999.99), 2),
                    f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                    random.choice(CATEGORIES),
                ])
            writer.writerows(rows)

            done = min(chunk_start + CHUNK_SIZE - 1, NUM_TRANSACTIONS)
            if done % 1_000_000 == 0 or done == NUM_TRANSACTIONS:
                elapsed = time.perf_counter() - start
                print(f"  ... {done:>10,} / {NUM_TRANSACTIONS:,}  ({elapsed:.1f}s)")

    size_mb = os.path.getsize(TRANSACTIONS_FILE) / (1024 * 1024)
    print(f"  [OK] transactions.csv written -- {size_mb:.1f} MB\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    overall = time.perf_counter()
    generate_users()
    generate_transactions()
    print(f"Done in {time.perf_counter() - overall:.1f}s total.")
