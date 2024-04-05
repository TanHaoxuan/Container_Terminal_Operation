import os
from dotenv import load_dotenv
from sqlalchemy import text, DDL, event
import sqlalchemy
from typing import List

load_dotenv('.env')
# Replace the following with your actual connection details
username = 'postgres'
password = '000000'
hostname = 'localhost:5432'
database_name = 'Project'

CONNECTION_STRING = f"postgresql+psycopg2://{username}:{password}@{hostname}/{database_name}"

NUM_OF_TABLES = 5
engine = sqlalchemy.create_engine(
    CONNECTION_STRING
)
db = engine.connect()

def drop_all_tables(db: sqlalchemy.engine.Connection) -> None:
    db.execute(text(
        '''
        DROP TABLE IF EXISTS credit_cards;
        DROP TABLE IF EXISTS rental;
        DROP TABLE IF EXISTS house_ratings;
        DROP TABLE IF EXISTS houses;
        DROP TABLE IF EXISTS users;
        '''
    ))

def create_all_tables(db: sqlalchemy.engine.Connection) -> None:
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS users(
            email VARCHAR(50) PRIMARY KEY,
            fname VARCHAR(32) NOT NULL,
            lname VARCHAR(32) NOT NULL,
            age INTEGER NOT NULL,
            password VARCHAR(32))'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS houses(
            id INTEGER PRIMARY KEY,
            location VARCHAR(32) NOT NULL,
            price FLOAT NOT NULL,
            num_room INT NOT NULL,
            owner_email VARCHAR(50),
            FOREIGN KEY (owner_email) REFERENCES users(email))'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS credit_cards(
            type VARCHAR(30) NOT NULL,
            number VARCHAR(32) PRIMARY KEY,
            email VARCHAR(50) NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email))'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS rental(
            email VARCHAR(50),
            houseid INTEGER,
            num_of_days INTEGER NOT NULL,
            date DATE NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email),
            FOREIGN KEY (houseid) REFERENCES houses(id),
            PRIMARY KEY(email, houseid))'''
    ))
    db.execute(text(
        '''SET datestyle = dmy  
        '''
    ))
    db.commit()
    print("ALL TABLES CREATED SUCCESSFULLY")

def load_dummy_data(db: sqlalchemy.engine.Connection) -> None:
    db.execute(text("".join(open("data/users.sql", "r").readlines())))
    db.execute(text("".join(open("data/houses.sql", "r").readlines())))
    db.execute(text("".join(open("data/credit_cards.sql", "r").readlines())))
    db.execute(text("".join(open("data/rental.sql", "r").readlines())))
    db.commit()
    print("ALL DATA POPULATED")

def check_table_exist(db: sqlalchemy.engine.Connection) -> bool:
    res = db.execute(text(
            '''SELECT count(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'public'
            '''
        ))
    return res.scalar() == NUM_OF_TABLES

def setup_database(db: sqlalchemy.engine.Connection) -> None:
    # if (check_table_exist(db)):
    #     return
    # if tables do not exist
    # create them
    drop_all_tables(db)
    create_all_tables(db)
    load_dummy_data(db)

def execute_sql(db: sqlalchemy.engine.Connection, command: str) -> List[sqlalchemy.engine.row.Row]:
    return db.execute(text(command)).fetchall()

def execute_update(db: sqlalchemy.engine.Connection, command: str):
    db.execute(text(command))
    return
# print(type(execute_sql(db,"SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'public'")[0]))
