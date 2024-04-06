from flask_cors import CORS
from flask import Flask, flash, redirect, request, Response, render_template, url_for, session
from helpers import credit_card_operation, check_credit_card, is_login

# Instantiate object app
app = Flask(__name__, template_folder='templates')
# Add cross origin security
CORS(app)
app.secret_key = 'the random string'

# connect to database
from db_manager import db, setup_database,execute_sql,execute_update
if (db == None):
    app.logger.error("Not able to connect to db")
    raise Exception("ERROR")
setup_database(db)
app.logger.info("Database created and populated")


@app.route("/")
def home():
    return redirect(url_for("logout"))

@app.route('/user', methods = ['GET', 'POST'])
def user():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        record = execute_sql(db,
            f"SELECT * FROM users WHERE email = '{email}' AND password = '{password}'")
        email_checker = execute_sql(db,
            f"SELECT * FROM users WHERE email = '{email}'")
        if len(record) == 0 and len(email_checker) == 1:
            flash(f"You have entered the wrong password for {email}.")
            return render_template("user/login.html")
        elif len(record) == 0:
            flash("Account doesnt exist!")
            return render_template("user/login.html")
        else:
            session["user"] = email
            flash("Logged in")
        return redirect(url_for("schedule_page"))

    return render_template("user/login.html")
    
@app.route('/register', methods = ['POST'])
def register():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        fname = request.form.get("fname")
        lname = request.form.get("lname")
        age = request.form.get("age")

        duplicate_account = execute_sql(db,
            f"SELECT * FROM users WHERE email = '{email}'") 
        if len(duplicate_account) == 1: 
            flash(f"Account already exists for {email}!")
            return redirect(url_for("user"))
        record = execute_update(db,
            f'''
            INSERT INTO users (fname, lname, email, age, password) values
            ('{fname}', '{lname}', '{email}', {age}, '{password}');
            ''')
        db.commit()
        flash(f"Yay {fname} you now have an account!!!")
    return redirect(url_for("user"))


@app.route('/logout')
@is_login
def logout():
    session.pop("user", None)
    return redirect(url_for("user"))

@app.route('/profile', methods=('GET', 'POST')) #char or int
@is_login
def update_profile():
    email = session["user"]

    if request.method == 'POST':
        password = request.form['password']
        credit_card = request.form['credit_card']
        credit_card_type = request.form['credit_card_type']
        credit_card_action = request.form['credit_card_action']
        if password:
            execute_update(db,f'''
                    UPDATE users 
                    SET password = '{password}'
                    WHERE email = '{email}'; 
                    ''')
            db.commit()
            flash('Updated your password!')
            
        ## Update credit card only
        elif (credit_card and credit_card_type):
            message = check_credit_card(credit_card_action, credit_card, credit_card_type, email)
            if message:
                flash(message)
            else: 
                credit_card_operation(credit_card_action, credit_card, credit_card_type, email)
                flash(f"Updated your credit card!")
        elif credit_card or credit_card_type:
            flash('Both Credit Card Number & Type required to Update!')
        elif not password and (credit_card and credit_card_type):
            flash('Nothing filled in. No changes made.')
            
    curr_credit_card_types = execute_sql(db, f'''
            SELECT * FROM credit_cards WHERE email = '{email}';
            ''')
    user = execute_sql(db, f'''
            SELECT * FROM users WHERE email = '{email}';
            ''')[0]
    return render_template('user/profile.html',
                curr_credit_card_types=curr_credit_card_types,
                user_fname=user.fname,
                user_lname=user.lname,
                user_email=user.email)

# Schedule page route
@app.route("/schedule")
@is_login
def schedule_page():
    return render_template('schedule/schedule_page.html')

# Record page route
@app.route("/record")
@is_login
def record_page():
    return render_template('record/record_page.html')

# Ship schedule form submission route
@app.route("/ship_schedule", methods=["GET", "POST"])
@is_login
def ship_schedule():
    if request.method == "POST":
        # Process form data and update the database as necessary
        ship_mmsi = request.form.get("Ship_MMSI")
        expected_arrival = request.form.get("Expected_arrival")
        expected_departure = request.form.get("Expected_departure")
        # Add to database
        flash("Ship schedule submitted successfully.")
        return redirect(url_for("schedule_page"))
    return render_template('ship_schedule.html')

# Container schedule form submission route
@app.route("/container_schedule", methods=["GET", "POST"])
@is_login
def container_schedule():
    if request.method == "POST":
        # Process form data and update the database as necessary
        container_id = request.form.get("Container_ID")
        ship_mmsi = request.form.get("type")  # The form has 'type', should it be 'ship_mmsi'?
        expected_start = request.form.get("Expected_start")
        expected_end = request.form.get("Expected_end")
        # Add to database
        flash("Container schedule submitted successfully.")
        return redirect(url_for("schedule_page"))
    return render_template('container_schedule.html')

# Ship record form submission route
@app.route("/ship_record", methods=["GET", "POST"])
@is_login
def ship_record():
    if request.method == "POST":
        # Process form data and update the database as necessary
        ship_mmsi = request.form.get("Ship_MMSI")
        actual_arrival = request.form.get("Actual_arrival")
        actual_departure = request.form.get("Actual_departure")
        # Add to database
        flash("Ship record submitted successfully.")
        return redirect(url_for("record_page"))
    return render_template('ship_record.html')

# Container record form submission route
@app.route("/container_record", methods=["GET", "POST"])
@is_login
def container_record():
    if request.method == "POST":
        # Process form data and update the database as necessary
        container_id = request.form.get("Container_ID")
        actual_start = request.form.get("Actual_start")
        actual_end = request.form.get("Actual_end")
        # Add to database
        flash("Container record submitted successfully.")
        return redirect(url_for("record_page"))
    return render_template('container_record.html')

# History route
@app.route("/history", methods=["GET", "POST"])
@is_login
def history():
    if request.method == "POST":
        # Search logic using the item submitted from the form
        item = request.form.get("item")
        # Search in the database for the item
        flash(f"Search for {item} completed.")
        # Render a template or redirect as needed
    return render_template('history/history.html')

if __name__ == "__main__":
    app.run(debug=True)
