# ==========================================================
#  TRANSPORT TICKET BOOKING SYSTEM  |  FINAL FLASK APP
# ==========================================================

from flask import Flask, render_template, request, redirect, session
import mysql.connector
import random, string, datetime

app = Flask(__name__)
app.secret_key = "secretkey123"   # session handling


# ==========================================================
#  DATABASE CONNECTION
# ==========================================================
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",              # 🔹 change if needed
        password="1507",  # 🔹 update with your MySQL password
        database="transport_db"
    )


# ==========================================================
#  HELPER FUNCTION
# ==========================================================
def table_info(mode):
    """Returns correct table and ID column for the given mode."""
    mode = mode.lower()
    if mode == "flight":
        return {"table": "flights", "id_col": "flight_id"}
    elif mode == "train":
        return {"table": "trains", "id_col": "train_id"}
    elif mode == "bus":
        return {"table": "buses", "id_col": "bus_id"}
    else:
        return None


# ==========================================================
#  LOGIN + SIGNUP
# ==========================================================
@app.route('/')
def home():
    return redirect('/login')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        con = get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            con.close()
            return "⚠️ Username already exists."
        cur.execute("INSERT INTO users (username, password) VALUES (%s,%s)", (username, password))
        con.commit()
        con.close()
        return redirect('/login')

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        con = get_connection()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        con.close()

        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            return redirect('/dashboard')
        else:
            return "❌ Invalid username or password."

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ==========================================================
#  DASHBOARD
# ==========================================================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('dashboard.html', username=session['username'])


# ==========================================================
#  BOOK TICKETS
# ==========================================================
@app.route('/book')
def book_home():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('book_select.html')


@app.route('/search/<mode>', methods=['GET', 'POST'])
def search(mode):
    """Search for flights, trains, or buses based on route and date."""
    if request.method == 'POST':
        from_city = request.form['from_city']
        to_city = request.form['to_city']
        date = request.form['date']

        try:
            day_name = datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        except Exception:
            day_name = ""

        info = table_info(mode)
        if not info:
            return "Invalid mode.", 400

        table = info['table']

        con = get_connection()
        cur = con.cursor(dictionary=True)

        # First search by day
        cur.execute(f"SELECT * FROM {table} WHERE from_city=%s AND to_city=%s AND day=%s",
                    (from_city, to_city, day_name))
        results = cur.fetchall()

        msg = ""
        if not results:
            msg = f"No {mode}s available on {day_name}. Showing all options for this route."
            cur.execute(f"SELECT * FROM {table} WHERE from_city=%s AND to_city=%s",
                        (from_city, to_city))
            results = cur.fetchall()
        con.close()

        return render_template('available_transports.html',
                               mode=mode,
                               transports=results,
                               msg=msg,
                               journey_date=date)

    return redirect('/book')


# ==========================================================
#  CONFIRM BOOKING
# ==========================================================
@app.route('/confirm/<mode>/<int:transport_id>', methods=['GET', 'POST'])
def confirm_booking(mode, transport_id):
    if 'user_id' not in session:
        return redirect('/login')

    info = table_info(mode)
    if not info:
        return "Invalid transport mode.", 400

    table = info['table']
    id_col = info['id_col']

    con = get_connection()
    cur = con.cursor(dictionary=True)

    # Fetch selected transport
    cur.execute(f"SELECT * FROM {table} WHERE {id_col} = %s", (transport_id,))
    transport = cur.fetchone()
    if not transport:
        con.close()
        return f"{mode.capitalize()} not found.", 404

    # Seat type options
    if mode == "flight":
        seat_types = ["Economy", "Premium Economy", "Business"]
    elif mode == "train":
        seat_types = ["1st AC", "2nd AC", "3rd AC", "Sleeper"]
    else:
        seat_types = ["AC Sleeper", "AC Chaircar", "Non AC Sleeper", "Non AC Chaircar"]

    if request.method == 'POST':
        name = request.form['name']
        age = int(request.form['age'])
        gender = request.form['gender']
        seat_type = request.form['seat_type']
        journey_date = request.form['journey_date']
        base_price = float(request.form['base_price'])

        # Seat price multipliers
        mult = {
            "Economy":1.0, "Premium Economy":1.4, "Business":1.8,
            "1st AC":1.6, "2nd AC":1.3, "3rd AC":1.0, "Sleeper":0.8,
            "AC Sleeper":1.7, "AC Chaircar":1.3,
            "Non AC Sleeper":1.4, "Non AC Chaircar":1.0
        }.get(seat_type, 1.0)

        price = round(base_price * mult, 2)
        ticket_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        cur.execute("""
            INSERT INTO tickets (user_id, mode, transport_id, name, age, gender, seat_type, journey_date, price)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (session['user_id'], mode, transport_id, name, age, gender, seat_type, journey_date, price))

        # Reduce available seats
        cur.execute(f"UPDATE {table} SET available_tickets = available_tickets - 1 WHERE {id_col}=%s", (transport_id,))
        con.commit()
        con.close()

        return render_template('ticket_confirmation.html',
                               ticket_id=ticket_code,
                               mode=mode,
                               name=name,
                               from_city=transport['from_city'],
                               to_city=transport['to_city'],
                               seat_type=seat_type,
                               journey_date=journey_date,
                               price=price)

    con.close()
    return render_template('confirm_booking.html',
                           mode=mode,
                           transport=transport,
                           seat_types=seat_types,
                           journey_date=request.args.get('journey_date', ''),
                           base_price=transport['base_price'])


# ==========================================================
#  VIEW TICKETS
# ==========================================================
@app.route('/tickets')
def view_tickets():
    if 'user_id' not in session:
        return redirect('/login')

    con = get_connection()
    cur = con.cursor(dictionary=True)
    cur.execute("SELECT * FROM tickets WHERE user_id=%s ORDER BY ticket_id DESC", (session['user_id'],))
    all_tickets = cur.fetchall()

    tickets = []
    for t in all_tickets:
        mode = t['mode']
        transport_id = t['transport_id']
        info = table_info(mode)
        if info:
            table = info['table']
            id_col = info['id_col']
            cur.execute(f"SELECT from_city, to_city FROM {table} WHERE {id_col}=%s", (transport_id,))
            trans = cur.fetchone()
            if trans:
                t['from_city'] = trans.get('from_city')
                t['to_city'] = trans.get('to_city')
            else:
                t['from_city'] = 'N/A'
                t['to_city'] = 'N/A'
        else:
            t['from_city'] = 'N/A'
            t['to_city'] = 'N/A'
        tickets.append(t)

    con.close()
    return render_template('view_tickets.html', tickets=tickets)


# ==========================================================
#  RUN SERVER
# ==========================================================
if __name__ == '__main__':
    app.run(debug=True)

