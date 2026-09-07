# ==========================================================
#  TRANSPORT TICKET BOOKING SYSTEM  |  SECURE FLASK APP
# ==========================================================

import os
import random
import string
import datetime
from functools import wraps
from datetime import date

from flask import Flask, render_template, request, redirect, session, flash, jsonify
from flask_wtf.csrf import CSRFProtect
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')
app.config['WTF_CSRF_ENABLED'] = True

# Initialize CSRF protection
csrf = CSRFProtect(app)


# ==========================================================
#  DATABASE CONNECTION
# ==========================================================
def get_connection():
    """Create and return a database connection using environment variables."""
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'transport_db')
    )


# ==========================================================
#  HELPER FUNCTIONS
# ==========================================================
VALID_MODES = {'flight', 'train', 'bus'}

MODE_TABLE_MAP = {
    'flight': {'table': 'flights', 'id_col': 'flight_id'},
    'train': {'table': 'trains', 'id_col': 'train_id'},
    'bus': {'table': 'buses', 'id_col': 'bus_id'},
}

SEAT_TYPE_MULTIPLIERS = {
    # Flights
    "Economy": 1.0,
    "Premium Economy": 1.4,
    "Business": 1.8,
    # Trains
    "1st AC": 1.6,
    "2nd AC": 1.3,
    "3rd AC": 1.0,
    "Sleeper": 0.8,
    # Buses
    "AC Sleeper": 1.7,
    "AC Chaircar": 1.3,
    "Non AC Sleeper": 1.4,
    "Non AC Chaircar": 1.0,
}

SEAT_TYPES_BY_MODE = {
    'flight': ["Economy", "Premium Economy", "Business"],
    'train': ["1st AC", "2nd AC", "3rd AC", "Sleeper"],
    'bus': ["AC Sleeper", "AC Chaircar", "Non AC Sleeper", "Non AC Chaircar"],
}

CITIES = [
    "Delhi", "Mumbai", "Chennai", "Kolkata", "Bengaluru",
    "Hyderabad", "Pune", "Ahmedabad", "Goa", "Jaipur"
]


def table_info(mode: str) -> dict | None:
    """Returns correct table and ID column for the given mode.
    Validates mode against whitelist to prevent SQL injection."""
    mode = mode.lower()
    if mode not in VALID_MODES:
        return None
    return MODE_TABLE_MAP[mode]


def login_required(f):
    """Decorator to require login for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


def validate_booking_input(name: str, age: int, gender: str, seat_type: str, mode: str) -> list[str]:
    """Validate booking form input. Returns list of error messages."""
    errors = []
    if not name or not name.strip():
        errors.append("Passenger name is required.")
    if not age or age < 1 or age > 120:
        errors.append("Age must be between 1 and 120.")
    if gender not in ('Male', 'Female', 'Other'):
        errors.append("Invalid gender selection.")
    if seat_type not in SEAT_TYPES_BY_MODE.get(mode, []):
        errors.append("Invalid seat type for selected transport mode.")
    return errors


# ==========================================================
#  AUTHENTICATION ROUTES
# ==========================================================
@app.route('/')
def home():
    return redirect('/login')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Input validation
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('signup.html')

        if len(username) > 50:
            flash('Username must be 50 characters or less.', 'error')
            return render_template('signup.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('signup.html')

        con = get_connection()
        cur = con.cursor()
        try:
            # Check if username exists
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                flash('Username already exists.', 'error')
                return render_template('signup.html')

            # Hash password before storing
            hashed_password = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, hashed_password)
            )
            con.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect('/login')
        except mysql.connector.Error as e:
            con.rollback()
            flash(f'Database error: {str(e)}', 'error')
            return render_template('signup.html')
        finally:
            con.close()

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html')

        con = get_connection()
        cur = con.cursor(dictionary=True)
        try:
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            user = cur.fetchone()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                flash(f'Welcome back, {user["username"]}!', 'success')
                return redirect('/dashboard')
            else:
                flash('Invalid username or password.', 'error')
        except mysql.connector.Error as e:
            flash(f'Database error: {str(e)}', 'error')
        finally:
            con.close()

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect('/login')


# ==========================================================
#  DASHBOARD
# ==========================================================
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session['username'])


# ==========================================================
#  BOOK TICKETS
# ==========================================================
@app.route('/book')
@login_required
def book_home():
    return render_template('book_select.html', cities=CITIES, today=date.today().isoformat())


@app.route('/search/<mode>', methods=['GET', 'POST'])
@login_required
def search(mode):
    """Search for flights, trains, or buses based on route and date."""
    # Validate mode against whitelist
    if mode not in VALID_MODES:
        flash('Invalid transport mode.', 'error')
        return redirect('/book')

    if request.method == 'POST':
        from_city = request.form.get('from_city', '').strip()
        to_city = request.form.get('to_city', '').strip()
        date = request.form.get('date', '').strip()

        if not from_city or not to_city or not date:
            flash('All fields are required.', 'error')
            return redirect('/book')

        if from_city == to_city:
            flash('Origin and destination cannot be the same.', 'error')
            return redirect('/book')

        try:
            journey_date = datetime.datetime.strptime(date, "%Y-%m-%d")
            day_name = journey_date.strftime("%A")
        except ValueError:
            flash('Invalid date format.', 'error')
            return redirect('/book')

        info = table_info(mode)
        table = info['table']

        con = get_connection()
        cur = con.cursor(dictionary=True)
        try:
            # First search by day
            cur.execute(
                f"SELECT * FROM {table} WHERE from_city=%s AND to_city=%s AND day=%s",
                (from_city, to_city, day_name)
            )
            results = cur.fetchall()

            msg = ""
            if not results:
                msg = f"No {mode}s available on {day_name}. Showing all options for this route."
                cur.execute(
                    f"SELECT * FROM {table} WHERE from_city=%s AND to_city=%s",
                    (from_city, to_city)
                )
                results = cur.fetchall()

            return render_template(
                'available_transports.html',
                mode=mode,
                transports=results,
                msg=msg,
                journey_date=date,
                from_city=from_city,
                to_city=to_city
            )
        except mysql.connector.Error as e:
            flash(f'Database error: {str(e)}', 'error')
            return redirect('/book')
        finally:
            con.close()

    return redirect('/book')


# ==========================================================
#  CONFIRM BOOKING
# ==========================================================
@app.route('/confirm/<mode>/<int:transport_id>', methods=['GET', 'POST'])
@login_required
def confirm_booking(mode, transport_id):
    # Validate mode against whitelist
    if mode not in VALID_MODES:
        flash('Invalid transport mode.', 'error')
        return redirect('/book')

    info = table_info(mode)
    if not info:
        flash('Invalid transport mode.', 'error')
        return redirect('/book')

    table = info['table']
    id_col = info['id_col']
    seat_types = SEAT_TYPES_BY_MODE.get(mode, [])

    con = get_connection()
    cur = con.cursor(dictionary=True)
    try:
        # Fetch selected transport
        cur.execute(f"SELECT * FROM {table} WHERE {id_col} = %s", (transport_id,))
        transport = cur.fetchone()

        if not transport:
            flash(f'{mode.capitalize()} not found.', 'error')
            return redirect('/book')

        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            age = request.form.get('age', type=int)
            gender = request.form.get('gender', '').strip()
            seat_type = request.form.get('seat_type', '').strip()
            journey_date = request.form.get('journey_date', '').strip()
            base_price = request.form.get('base_price', type=float)

            # Validate input
            errors = validate_booking_input(name, age, gender, seat_type, mode)
            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template(
                    'confirm_booking.html',
                    mode=mode,
                    transport=transport,
                    seat_types=seat_types,
                    journey_date=journey_date,
                    base_price=base_price or transport['base_price']
                )

            # Calculate price
            multiplier = SEAT_TYPE_MULTIPLIERS.get(seat_type, 1.0)
            price = round((base_price or transport['base_price']) * multiplier, 2)
            ticket_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

            # Atomic booking: check availability and decrement in one query
            cur.execute(
                f"UPDATE {table} SET available_tickets = available_tickets - 1 "
                f"WHERE {id_col}=%s AND available_tickets > 0",
                (transport_id,)
            )

            if cur.rowcount == 0:
                flash('Sorry, this transport is no longer available.', 'error')
                con.rollback()
                return render_template(
                    'confirm_booking.html',
                    mode=mode,
                    transport=transport,
                    seat_types=seat_types,
                    journey_date=journey_date,
                    base_price=base_price or transport['base_price']
                )

            # Insert ticket record
            cur.execute("""
                INSERT INTO tickets (user_id, mode, transport_id, name, age, gender, seat_type, journey_date, price)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (session['user_id'], mode, transport_id, name, age, gender, seat_type, journey_date, price))

            con.commit()

            return render_template(
                'ticket_confirmation.html',
                ticket_id=ticket_code,
                mode=mode,
                name=name,
                from_city=transport['from_city'],
                to_city=transport['to_city'],
                seat_type=seat_type,
                journey_date=journey_date,
                price=price
            )

        # GET request - show confirmation form
        journey_date = request.args.get('journey_date', '')
        return render_template(
            'confirm_booking.html',
            mode=mode,
            transport=transport,
            seat_types=seat_types,
            journey_date=journey_date,
            base_price=transport['base_price']
        )
    except mysql.connector.Error as e:
        con.rollback()
        flash(f'Database error: {str(e)}', 'error')
        return redirect('/book')
    finally:
        con.close()


# ==========================================================
#  VIEW TICKETS
# ==========================================================
@app.route('/tickets')
@login_required
def view_tickets():
    # Get filter parameters
    filter_mode = request.args.get('mode', '').strip()
    filter_status = request.args.get('status', '').strip()
    filter_date_from = request.args.get('date_from', '').strip()
    filter_date_to = request.args.get('date_to', '').strip()

    con = get_connection()
    cur = con.cursor(dictionary=True)
    try:
        # Build query with filters
        query = "SELECT * FROM tickets WHERE user_id=%s"
        params = [session['user_id']]

        if filter_mode:
            query += " AND mode=%s"
            params.append(filter_mode)
        if filter_status:
            query += " AND status=%s"
            params.append(filter_status)
        if filter_date_from:
            query += " AND journey_date >= %s"
            params.append(filter_date_from)
        if filter_date_to:
            query += " AND journey_date <= %s"
            params.append(filter_date_to)

        query += " ORDER BY ticket_id DESC"

        cur.execute(query, tuple(params))
        all_tickets = cur.fetchall()

        tickets = []
        for t in all_tickets:
            mode = t['mode']
            transport_id = t['transport_id']
            info = table_info(mode)
            if info:
                table = info['table']
                id_col = info['id_col']
                # Parameterized query to prevent SQL injection
                cur.execute(
                    f"SELECT from_city, to_city FROM {table} WHERE {id_col}=%s",
                    (transport_id,)
                )
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

        return render_template('view_tickets.html', tickets=tickets)
    except mysql.connector.Error as e:
        flash(f'Database error: {str(e)}', 'error')
        return render_template('view_tickets.html', tickets=[])
    finally:
        con.close()


# ==========================================================
#  CANCEL TICKET
# ==========================================================
@app.route('/tickets/cancel/<int:ticket_id>', methods=['POST'])
@login_required
def cancel_ticket(ticket_id):
    con = get_connection()
    cur = con.cursor(dictionary=True)
    try:
        # Verify ownership and get details
        cur.execute("SELECT * FROM tickets WHERE ticket_id=%s AND user_id=%s",
                   (ticket_id, session['user_id']))
        ticket = cur.fetchone()

        if not ticket:
            flash('Ticket not found.', 'error')
            return redirect('/tickets')

        if ticket.get('status') == 'cancelled':
            flash('Ticket already cancelled.', 'warning')
            return redirect('/tickets')

        # Restore seat availability
        info = table_info(ticket['mode'])
        if info:
            cur.execute(
                f"UPDATE {info['table']} SET available_tickets = available_tickets + 1 "
                f"WHERE {info['id_col']}=%s",
                (ticket['transport_id'],)
            )

        # Mark ticket as cancelled
        cur.execute("UPDATE tickets SET status='cancelled' WHERE ticket_id=%s", (ticket_id,))
        con.commit()
        flash('Ticket cancelled successfully. Seat restored.', 'success')
    except mysql.connector.Error as e:
        con.rollback()
        flash(f'Database error: {str(e)}', 'error')
    finally:
        con.close()
    return redirect('/tickets')


# ==========================================================
#  API ENDPOINTS
# ==========================================================
@app.route('/api/ticket-stats')
@login_required
def api_ticket_stats():
    con = get_connection()
    cur = con.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) as cancelled
            FROM tickets WHERE user_id=%s
        """, (session['user_id'],))
        result = cur.fetchone()
        return jsonify({
            'total': result['total'] or 0,
            'active': result['active'] or 0,
            'cancelled': result['cancelled'] or 0
        })
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        con.close()


# ==========================================================
#  RUN SERVER
# ==========================================================
if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode)