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
        DROP TABLE IF EXISTS movement;
        DROP TABLE IF EXISTS ship_schedule;
        DROP TABLE IF EXISTS ship;
        DROP TABLE IF EXISTS container;
        DROP TABLE IF EXISTS berth;
        DROP TABLE IF EXISTS yard_location;
        '''
    ))

def create_all_tables(db: sqlalchemy.engine.Connection) -> None:
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS ship (
            mmsi INT PRIMARY KEY,
            name VARCHAR(255),
            flag VARCHAR(100),
            length DECIMAL(10, 2),
            width DECIMAL(10, 2)
        );'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS container (
            iso_id VARCHAR(100) PRIMARY KEY,
            weight DECIMAL(10, 2),
            content VARCHAR(255),
            owner VARCHAR(255)
        );'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS berth (
            berth_id INT PRIMARY KEY,
            length DECIMAL(10, 2),
            depth DECIMAL(10, 2)
        );'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS yard_location (
            bay INT,
            row INT,
            tier INT,
            PRIMARY KEY (bay, row, tier)
        );'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS movement (
            movement_id SERIAL PRIMARY KEY,
            e_start_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            e_end_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            a_start_datetime TIMESTAMP WITHOUT TIME ZONE,
            a_end_datetime TIMESTAMP WITHOUT TIME ZONE,
            type VARCHAR(10) NOT NULL CHECK (type IN ('Load', 'Unload', 'Transfer')),
            container_iso_id VARCHAR(100) NOT NULL,
            ship_mmsi INTEGER,
            src_bay INTEGER,
            src_row INTEGER,
            src_tier INTEGER,
            des_bay INTEGER,
            des_row INTEGER,
            des_tier INTEGER,
            FOREIGN KEY (container_iso_id) REFERENCES container(iso_id),
            FOREIGN KEY (ship_mmsi) REFERENCES ship(mmsi),
            FOREIGN KEY (src_bay, src_row, src_tier) REFERENCES yard_location(bay, row, tier),
            FOREIGN KEY (des_bay, des_row, des_tier) REFERENCES yard_location(bay, row, tier),
            CHECK (e_start_datetime < e_end_datetime)
        );'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS ship_schedule (
            schedule_id SERIAL PRIMARY KEY,
            ship_mmsi INTEGER NOT NULL,
            berth_id INTEGER NOT NULL,
            e_start_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            e_end_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            a_start_datetime TIMESTAMP WITHOUT TIME ZONE,
            a_end_datetime TIMESTAMP WITHOUT TIME ZONE,
            FOREIGN KEY (ship_mmsi) REFERENCES ship(mmsi),
            FOREIGN KEY (berth_id) REFERENCES berth(berth_id),
            CHECK (e_start_datetime < e_end_datetime)
        );'''
    ))
    db.execute(text(
        '''CREATE OR REPLACE FUNCTION prevent_time_conflict_func()
        RETURNS TRIGGER AS $$
        DECLARE
            conflict_count INT;
        BEGIN
            -- Check for time overlap conflicts
            SELECT COUNT(*)
            INTO conflict_count
            FROM ship_schedule
            WHERE ship_mmsi = NEW.ship_mmsi
            AND ((NEW.e_start_datetime BETWEEN e_start_datetime AND e_end_datetime)
            OR (NEW.e_end_datetime BETWEEN e_start_datetime AND e_end_datetime));

            IF conflict_count > 0 THEN
                RAISE EXCEPTION 'Time schedule conflict for ship % for %', NEW.ship_mmsi, NEW.e_start_datetime;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER prevent_time_conflict
        BEFORE INSERT ON ship_schedule
        FOR EACH ROW
        EXECUTE FUNCTION prevent_time_conflict_func();'''
    ))

    db.execute(text(
        '''SET datestyle = dmy  
        '''
    ))
    db.commit()
    print("ALL TABLES CREATED SUCCESSFULLY")

def load_dummy_data(db: sqlalchemy.engine.Connection) -> None:
    db.execute(text("".join(open("sql_data/ships.sql", "r").readlines())))
    db.execute(text("".join(open("sql_data/containers.sql", "r").readlines())))
    db.execute(text("".join(open("sql_data/berths.sql", "r").readlines())))
    db.execute(text("".join(open("sql_data/yard_locations.sql", "r").readlines())))
    #db.execute(text("".join(open("sql_data/ship_schedule.sql", "r").readlines())))
    db.execute(text("".join(open("sql_data/movements.sql", "r").readlines())))
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
