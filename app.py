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
        return redirect(url_for("rentals"))

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

@app.route("/bookings", methods = ['GET'])
def bookings():
    email = session["user"]
    
    user_visited_all = execute_sql(db, f'''
            SELECT *
            FROM users as u
            WHERE NOT EXISTS (
                SELECT h.id
                FROM houses as h
                EXCEPT                    
                SELECT r.houseid
                FROM rental as r
                WHERE u.email=r.email
            );                    
            ''').__len__()
    
    unique_booking_count = execute_sql(db, f'''
            SELECT count(*)
            FROM rental as r, houses as h
            WHERE r.email = '{email}' AND h.id=r.houseid;
            ''')[0]

    unique_houses_not_booked = execute_sql(db, f'''
            SELECT count(*)
            FROM
                (SELECT id
                FROM houses
                EXCEPT
                SELECT r.houseid
                FROM rental as r, houses as h
                WHERE r.email = '{email}' AND h.id=r.houseid) as list
            ;
            ''')[0]
    
    rentals = execute_sql(db, f'''
            SELECT h.location, h.price, r.num_of_days, r.date
            FROM rental as r, houses as h
            WHERE r.email = '{email}' AND h.id=r.houseid
            ORDER BY r.date desc;
            ''')
    return render_template('bookings/index.html',
                rents=rentals,
                unique_booking_count=unique_booking_count,
                unique_houses_not_booked=unique_houses_not_booked,
                user_visited_all=user_visited_all)

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

@app.route('/listings')
@is_login
def get_my_listings():
    email = session["user"]
    listings = execute_sql(db,
        f'''SELECT h.id ,h.location, h.price, h.num_room
        FROM houses h, users u 
        WHERE u.email = h.owner_email AND 
        u.email = '{email}' 
        ORDER BY h.location DESC
        ''')
    db.commit()
    return render_template('listings/index.html', 
                           listings=listings)

@app.route('/listings/update/<int:id>', methods=('GET', 'POST'))
@is_login
def update_listing(id):
    listing = execute_sql(db, f'''
        SELECT * FROM houses WHERE id = {id};''')[0]
    db.commit()
    email = session["user"]
    if request.method == 'POST':
        location = request.form['location']
        price = request.form['price']
        num_room = request.form['num_room']
        execute_update(db,f'''
                UPDATE houses 
                SET location = '{location}',
                price = {price},
                num_room = {num_room} 
                WHERE owner_email = '{email}' AND
                id = {id}; 
                ''')
        db.commit()
        return redirect(url_for('get_my_listings'))

    return render_template('listings/update.html',
                           listing=listing)
        
@app.route('/listings/create', methods = ['GET', 'POST'])
@is_login
def create_listing():
    email = session["user"]
    if request.method == 'POST':
        location = request.form.get('location')
        price = request.form.get('price')
        num_room = request.form.get('num_room')
        id = execute_sql(db, f'''SELECT id FROM houses ORDER BY id DESC;''')[0][0] + 1
        execute_update(db,f'''
        INSERT INTO houses (id, location, price, num_room, owner_email) values
        ({id},'{location}', {price}, {num_room}, '{email}');
        ''')
        db.commit()
        return redirect(url_for('get_my_listings'))
    
    return render_template('listings/create.html')

@app.route('/listings/<int:id>/delete', methods=['POST'])
@is_login
def delete_listing(id):
    execute_update(db, f'''
    DELETE FROM houses WHERE id = {id}; 
    ''')
    db.commit()
    return redirect(url_for('get_my_listings'))
    
@app.route('/rentals', methods = ['GET', 'POST'])
@is_login
def rentals():
    rental = execute_sql(db,
        f'''SELECT * FROM houses
            ORDER BY id desc'''
    )
    return render_template('rent/index.html', rental=rental)

@app.route('/create_rental/<id>', methods = ['GET', 'POST'])
@is_login
def create_rental(id):
    email = session['user']
    cards = execute_sql(db,
            f'''SELECT * FROM credit_cards WHERE email = '{email}';
            ''')
    if len(cards) == 0:
        flash('You do not have any credit cards, please add one to rent a house.')
        return redirect(url_for('update_profile'))
    
    house = execute_sql(db,
            f'''SELECT * FROM houses WHERE id = {id};
            ''')[0]
    if request.method == 'GET':
        return render_template('rent/create.html', cards = cards, house=house)
    
    elif request.method == "POST":
        cc_num = request.form['credit_card_num']
        date = request.form['booking_date']
        num_of_days = int(request.form['num_of_days'])
        
        execute_update(db,
            f'''INSERT INTO rental (email,houseid,num_of_days,date)
            VALUES ('{email}',{id},{num_of_days},'{date}');
            ''')
        flash(f"Successful booking of {house.location} at cost: {num_of_days*house.price}")
        return redirect(url_for('bookings'))

if __name__ == "__main__":
    app.run()