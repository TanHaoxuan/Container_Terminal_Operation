from flask_cors import CORS
from functools import wraps
from flask import Flask, flash, redirect, request, Response, render_template, url_for, session
from sqlalchemy.exc import SQLAlchemyError 

# Instantiate object app
app = Flask(__name__, template_folder='templates')
# Add cross origin security
CORS(app)
app.secret_key = 'the random string'

# connect to database
from db_manager import db, setup_database,execute_sql,execute_update, execute_sql_fetch
if (db == None):
    app.logger.error("Not able to connect to db")
    raise Exception("ERROR")
setup_database(db)
app.logger.info("Database created and populated")

# Login function
def is_login(f):
    @wraps(f)
    def decorated_func(*args, **kwargs):
        if "user" in session:
            return f(*args, **kwargs)
        else:
            flash("Please log in before using the system")
            return redirect(url_for("user"))
    return decorated_func


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
        try:
            # Process form data and update the database as necessary
            ship_mmsi = request.form.get("Ship_MMSI")
            expected_arrival = request.form.get("Expected_arrival")
            expected_departure = request.form.get("Expected_departure")
            #find berth_id 
            berth_id = execute_sql(db, 
                        f"""
                        SELECT berth_id
                        FROM berth
                        EXCEPT
                        SELECT s.berth_id
                        FROM ship_schedule s
                        WHERE (s.e_departure > DATE '{expected_arrival}' OR s.a_departure > DATE '{expected_arrival}')
                        AND (s.e_arrival < DATE '{expected_departure}' OR s.a_arrival < DATE '{expected_departure}');
                        """)[0][0]
            
            # Add to database
            execute_update(db,
                f'''
                INSERT INTO ship_schedule (ship_mmsi, berth_id, e_arrival, e_departure) values
                ({ship_mmsi}, {berth_id}, '{expected_arrival}', '{expected_departure}');
                ''')
            db.commit()
            schedule_id = execute_sql(db, 
                        f"""
                        SELECT schedule_id
                        FROM ship_schedule s
                        WHERE s.ship_mmsi = '{ship_mmsi}' AND s.berth_id = '{berth_id}' AND s.e_arrival = '{expected_arrival}' AND s.e_departure = '{expected_departure}';
                        """)[0][0]
            flash(f"Ship schedule submitted successfully. schedule_id = {schedule_id}")
            return redirect(url_for("schedule_page"))
        except SQLAlchemyError as e:
            db.rollback()
            error_message = str(e)
            flash("An error occurred: " + error_message, "error")
            return render_template('schedule/ship_schedule.html')
    return render_template('schedule/ship_schedule.html')

# Container schedule form submission route
@app.route("/container_schedule", methods=["GET", "POST"])
@is_login
def container_schedule():
    if request.method == "POST":
        try:
            # Process form data and update the database as necessary
            container_id = request.form.get("Container_ID")
            movement_type = request.form.get("movement_type")
            expected_start = request.form.get("Expected_start")
            expected_end = request.form.get("Expected_end")
            if movement_type == "Unload":
                ship_mmsi = request.form.get("Ship_MMSI")
                des_bay = request.form.get("des_bay")
                des_row = request.form.get("des_row")
                des_tier = request.form.get("des_tier")
                execute_update(db,
                f'''
                INSERT INTO movement (container_iso_id,type,e_start,e_end,ship_mmsi,des_bay,des_row,des_tier) values
                ('{container_id}', '{movement_type}', '{expected_start}', '{expected_end}', {ship_mmsi}, {des_bay}, {des_row}, {des_tier});
                ''')
                db.commit()
            elif movement_type == "Load":
                ship_mmsi = request.form.get("Ship_MMSI")
                #find current location of the container  
                src_bay = execute_sql(db,  
                        f"""
                        -- Find out where the container is last at
                        SELECT m.des_bay, m.des_row, m.des_tier
                        FROM movement m, (
                            SELECT container_iso_id, GREATEST(MAX(e_end), MAX(a_end)) AS latest
                            FROM movement
                            WHERE container_iso_id = '{container_id}'
                            AND (type='Transfer' OR type='Unload')
                            GROUP BY container_iso_id
                        ) l
                        WHERE (l.latest = m.a_end OR l.latest = m.e_end)
                        AND m.container_iso_id = l.container_iso_id;
                        """)[0][0] 
                src_row = execute_sql(db,  
                        f"""
                        -- Find out where the container is last at
                        SELECT m.des_bay, m.des_row, m.des_tier
                        FROM movement m, (
                            SELECT container_iso_id, GREATEST(MAX(e_end), MAX(a_end)) AS latest
                            FROM movement
                            WHERE container_iso_id = '{container_id}'
                            AND (type='Transfer' OR type='Unload')
                            GROUP BY container_iso_id
                        ) l
                        WHERE (l.latest = m.a_end OR l.latest = m.e_end)
                        AND m.container_iso_id = l.container_iso_id;
                        """)[0][1] 
                src_tier =execute_sql(db,  
                        f"""
                        -- Find out where the container is last at
                        SELECT m.des_bay, m.des_row, m.des_tier
                        FROM movement m, (
                            SELECT container_iso_id, GREATEST(MAX(e_end), MAX(a_end)) AS latest
                            FROM movement
                            WHERE container_iso_id = '{container_id}'
                            AND (type='Transfer' OR type='Unload')
                            GROUP BY container_iso_id
                        ) l
                        WHERE (l.latest = m.a_end OR l.latest = m.e_end)
                        AND m.container_iso_id = l.container_iso_id;
                        """)[0][2] 
                execute_update(db, 
                f''' 
                INSERT INTO movement (container_iso_id,type,e_start,e_end,ship_mmsi,src_bay,src_row,src_tier) values 
                ('{container_id}', '{movement_type}', '{expected_start}', '{expected_end}', {ship_mmsi}, {src_bay}, {src_row}, {src_tier}); 
                ''')
                db.commit()
            elif movement_type == "Transfer":
                des_bay = request.form.get("des_bay")
                des_row = request.form.get("des_row")
                des_tier = request.form.get("des_tier")
                #find current location of the container  
                src_bay = execute_sql(db,  
                        f"""
                        -- Find out where the container is last at
                        SELECT m.des_bay, m.des_row, m.des_tier
                        FROM movement m, (
                            SELECT container_iso_id, GREATEST(MAX(e_end), MAX(a_end)) AS latest
                            FROM movement
                            WHERE container_iso_id = '{container_id}'
                            AND (type='Transfer' OR type='Unload')
                            GROUP BY container_iso_id
                        ) l
                        WHERE (l.latest = m.a_end OR l.latest = m.e_end)
                        AND m.container_iso_id = l.container_iso_id;
                        """)[0][0] 
                src_row = execute_sql(db,  
                        f"""
                        -- Find out where the container is last at
                        SELECT m.des_bay, m.des_row, m.des_tier
                        FROM movement m, (
                            SELECT container_iso_id, GREATEST(MAX(e_end), MAX(a_end)) AS latest
                            FROM movement
                            WHERE container_iso_id = '{container_id}'
                            AND (type='Transfer' OR type='Unload')
                            GROUP BY container_iso_id
                        ) l
                        WHERE (l.latest = m.a_end OR l.latest = m.e_end)
                        AND m.container_iso_id = l.container_iso_id;
                        """)[0][1] 
                src_tier =execute_sql(db,  
                        f"""
                        -- Find out where the container is last at
                        SELECT m.des_bay, m.des_row, m.des_tier
                        FROM movement m, (
                            SELECT container_iso_id, GREATEST(MAX(e_end), MAX(a_end)) AS latest
                            FROM movement
                            WHERE container_iso_id = '{container_id}'
                            AND (type='Transfer' OR type='Unload')
                            GROUP BY container_iso_id
                        ) l
                        WHERE (l.latest = m.a_end OR l.latest = m.e_end)
                        AND m.container_iso_id = l.container_iso_id;
                        """)[0][2] 
                execute_update(db, 
                    f''' 
                    INSERT INTO movement (container_iso_id,type,e_start,e_end,src_bay,src_row,src_tier,des_bay,des_row,des_tier) values 
                    ('{container_id}', '{movement_type}', '{expected_start}', '{expected_end}', {src_bay}, {src_row}, {src_tier}, {des_bay}, {des_row}, {des_tier}); 
                    ''') 
                db.commit()
            movement_id = execute_sql(db, 
                    f"""
                    SELECT movement_id
                    FROM movement m
                    WHERE m.container_iso_id = '{container_id}' AND m.type = '{movement_type}' AND m.e_start = '{expected_start}' AND m.e_end = '{expected_end}';
                    """)[0][0]
            flash(f"Container schedule submitted successfully. movement_id = {movement_id}")
            return redirect(url_for("schedule_page"))
        except SQLAlchemyError as e:
            db.rollback()
            error_message = str(e)
            flash("An error occurred: " + error_message, "error")
            return render_template('schedule/container_schedule.html')
    return render_template('schedule/container_schedule.html')

# Ship record form submission route
@app.route("/ship_record", methods=["GET", "POST"])
@is_login
def ship_record():
    if request.method == "POST":
        try:
            # Process form data and update the database as necessary
            schedule_id = request.form.get("schedule_id")
            schedule_type = request.form.get("schedule_type")
            if schedule_type == "Arrival":
                actual_arrival = request.form.get("Actual_arrival")
                execute_update(db,f'''
                        UPDATE ship_schedule 
                        SET a_arrival = '{actual_arrival}'
                        WHERE schedule_id = '{schedule_id}'; 
                        ''')
                db.commit()
            elif schedule_type == "Departure":
                actual_departure = request.form.get("Actual_departure")
                execute_update(db,f'''
                        UPDATE ship_schedule 
                        SET a_departure = '{actual_departure}'
                        WHERE schedule_id = '{schedule_id}'; 
                        ''')
                db.commit()
            # Add to database
            flash("Ship record submitted successfully.")
            return redirect(url_for("record_page"))
        except SQLAlchemyError as e:
            db.rollback()
            error_message = str(e)
            flash("An error occurred: " + error_message, "error")
            return render_template('record/ship_record.html')
    return render_template('record/ship_record.html')

# Container record form submission route
@app.route("/container_record", methods=["GET", "POST"])
@is_login
def container_record():
    if request.method == "POST":
        try:
            # Process form data and update the database as necessary
            movement_id = request.form.get("movement_id")
            schedule_type = request.form.get("schedule_type")
            if schedule_type == "Actual_start":
                actual_start = request.form.get("Actual_start")
                execute_update(db,f'''
                        UPDATE movement 
                        SET a_start = '{actual_start}'
                        WHERE movement_id = {movement_id}; 
                        ''')
                db.commit()
            elif schedule_type == "Actual_end":
                actual_end = request.form.get("Actual_end")
                execute_update(db,f'''
                        UPDATE movement 
                        SET a_end = '{actual_end}'
                        WHERE movement_id = {movement_id}; 
                        ''')
                db.commit()
            # Add to database
            flash("Container record submitted successfully.")
            return redirect(url_for("record_page"))
        except SQLAlchemyError as e:
            db.rollback()
            error_message = str(e)
            flash("An error occurred: " + error_message, "error")
            return render_template('record/container_record.html')
    return render_template('record/container_record.html')

# History route
@app.route("/history", methods=["GET", "POST"])
@is_login
def history():
    if request.method == "POST":
        # Search logic using the item submitted from the form
        item = request.form.get("item")
        if item == "Ship":
            ship_data, column_names = execute_sql_fetch(db,
                    f'''
                    SELECT * FROM ship;
                    ''')
            db.commit()
            # Render a template or redirect as needed
            return render_template('history/history.html', items = ship_data,  columns=column_names)
        elif item == "Container":
            container_data, column_names = execute_sql_fetch(db,
                    f'''
                    SELECT * FROM container;
                    ''')
            db.commit()
            # Render a template or redirect as needed
            return render_template('history/history.html', items = container_data,  columns=column_names)
        elif item == "Movement":
            movement_data, column_names = execute_sql_fetch(db,
                    f'''
                    SELECT * FROM movement;
                    ''')
            db.commit()
            # Render a template or redirect as needed
            return render_template('history/history.html', items = movement_data,  columns=column_names)
        elif item == "Ship_Schedule":
            ship_schdule_data, column_names = execute_sql_fetch(db,
                    f'''
                    SELECT * FROM ship_schedule;
                    ''')
            db.commit()
            # Render a template or redirect as needed
            return render_template('history/history.html', items = ship_schdule_data,  columns=column_names)
 
    return render_template('history/history.html')

if __name__ == "__main__":
    app.run(debug=True)
