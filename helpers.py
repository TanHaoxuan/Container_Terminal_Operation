from functools import wraps
from flask import flash, redirect, session, url_for
from db_manager import execute_sql, execute_update, db

def is_login(f):
    @wraps(f)
    def decorated_func(*args, **kwargs):
        if "user" in session:
            return f(*args, **kwargs)
        else:
            flash("Please log in before using the system")
            return redirect(url_for("user"))
    return decorated_func

def credit_card_operation(action, number, type, email):
    if action == "DELETE":
        execute_update(db,f'''
                DELETE from credit_cards
                WHERE email = '{email}' and number = '{number}' and type='{type}';
                ''')
    elif action == "ADD":
        execute_update(db,f'''
                INSERT INTO credit_cards(type,number,email) 
                values('{type}','{number}','{email}');
                ''')
    db.commit()
    return

def check_credit_card(action, number, type, email):
    check = execute_sql(db, f'''
            SELECT * FROM credit_cards
            WHERE email = '{email}' AND type = '{type}' AND number='{number}';       
            ''')
    
    if action == "DELETE":
        if len(check) == 0:
            return f"Credit Card Type does not exist yet in your account. Unable to DELETE!"
        else:
            return ""
    elif action == "ADD":
        if len(check):
            return f"Credit Card of {type} and {number} already exists! Unable to ADD."
        else:
            return ""
    return
