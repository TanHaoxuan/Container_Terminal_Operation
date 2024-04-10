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
'''
def find_available_berths(arrival: str, departure: str, cursor) -> list[int]:
    """
    Returns a list of integers representing the berth_id of an availble berths
    """
    sql_query = f"""
        SELECT berth_id
        FROM berth
        EXCEPT
        SELECT s.berth_id
        FROM ship_schedule s
        WHERE (s.e_departure > {arrival} OR s.a_departure > {arrival})
        AND (s.e_arrival < {departure} OR s.a_arrival < {departure});
        """
    
    cursor.execute(sql_query)
    available_berths = cursor.fetchall()
    
    return available_berths

def find_available_yard_locations(start: str, cursor) -> list[tuple]:
    """
    Returns a list of tuples representing the bay, row, tier of availble yard locations
    """
    sql_query = f"""
        -- Check for available yard locations
        SELECT bay, row, tier
        FROM yard_location
        EXCEPT
        SELECT l1.bay, l1.row, l1.tier
        FROM movement m1, (
            -- Latest operation timing concerning each yard location (if any)
            SELECT y.bay, y.row, y.tier, GREATEST(MAX(m.e_end), MAX(m.a_end)) AS latest
            FROM movement m, yard_location y
            WHERE ((y.bay=m.src_bay AND y.row=m.src_row AND y.tier=m.src_tier)
            OR (y.bay=m.des_bay AND y.row=m.des_row AND y.tier=m.des_tier))
            AND (m.a_end <= {start} OR m.e_end <= {start})
            GROUP BY (y.bay, y.row, y.tier)
        ) l1
        WHERE (m1.a_end = l1.latest OR m1.e_end = l1.latest)
        AND m1.des_bay=l1.bay AND m1.des_row=l1.row AND m1.des_tier=l1.tier
        AND (m1.type = 'Unload' OR m1.type = 'Transfer')
        );
        """
    
    cursor.execute(sql_query)
    available_yard_locations = cursor.fetchall()

    return available_yard_locations
'''
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
