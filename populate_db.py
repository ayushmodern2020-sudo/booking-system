# ===============================================================
#  POPULATE TRANSPORT DATABASE SCRIPT
# ===============================================================

import os
import random
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------- CONNECT TO DATABASE ----------
con = mysql.connector.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'transport_db')
)

cur = con.cursor()

# ---------- BASIC DATA ----------
cities = ["Delhi", "Mumbai", "Chennai", "Kolkata", "Bengaluru", "Hyderabad", "Pune", "Ahmedabad", "Goa", "Jaipur"]
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
times = ["06:00 AM", "09:30 AM", "12:00 PM", "03:45 PM", "06:00 PM", "09:15 PM", "11:30 PM"]

# ---------- CLEAR OLD DATA ----------
cur.execute("DELETE FROM flights")
cur.execute("DELETE FROM trains")
cur.execute("DELETE FROM buses")

# ---------- FLIGHTS ----------
for i in range(300):  # creates 300 random flight records
    from_city, to_city = random.sample(cities, 2)
    name = f"AirIndia {random.randint(100, 999)}"
    day = random.choice(days)
    time = random.choice(times)
    price = random.randint(4000, 12000)
    seats = random.randint(50, 150)
    cur.execute("""
        INSERT INTO flights (name, from_city, to_city, day, time, base_price, available_tickets)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (name, from_city, to_city, day, time, price, seats))

print("✅ Inserted 300 flights")

# ---------- TRAINS ----------
for i in range(250):  # creates 250 train records
    from_city, to_city = random.sample(cities, 2)
    name = f"Express {random.randint(10000, 99999)}"
    day = random.choice(days)
    time = random.choice(times)
    price = random.randint(500, 2000)
    seats = random.randint(100, 300)
    cur.execute("""
        INSERT INTO trains (name, from_city, to_city, day, time, base_price, available_tickets)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (name, from_city, to_city, day, time, price, seats))

print("✅ Inserted 250 trains")

# ---------- BUSES ----------
for i in range(200):  # creates 200 bus records
    from_city, to_city = random.sample(cities, 2)
    name = f"RedBus {random.randint(1000, 9999)}"
    day = random.choice(days)
    time = random.choice(times)
    price = random.randint(300, 1000)
    seats = random.randint(20, 60)
    cur.execute("""
        INSERT INTO buses (name, from_city, to_city, day, time, base_price, available_tickets)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (name, from_city, to_city, day, time, price, seats))

print("✅ Inserted 200 buses")

# ---------- SAVE AND CLOSE ----------
con.commit()
con.close()

print("🎉 Database successfully populated with sample data!")