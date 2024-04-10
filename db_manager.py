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
            DROP TRIGGER IF EXISTS prevent_schedule_time_conflict ON ship_schedule;
            DROP TRIGGER IF EXISTS prevent_movement_time_conflict ON movement;
            DROP TRIGGER IF EXISTS check_last_operation_not_load ON movement;
            DROP TRIGGER IF EXISTS check_ship_at_berth_schedule ON movement;
            DROP TRIGGER IF EXISTS check_ship_at_berth_operation ON movement;
            DROP TRIGGER IF EXISTS check_container_at_correct_location_during_operation ON movement;

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
        '''CREATE TABLE IF NOT EXISTS users(
            email VARCHAR(50) PRIMARY KEY,
            fname VARCHAR(32) NOT NULL,
            lname VARCHAR(32) NOT NULL,
            age INTEGER NOT NULL,
            password VARCHAR(32))'''
    ))
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
            iso_id VARCHAR(11) PRIMARY KEY,
            content VARCHAR(255) NOT NULL
        );'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS berth (
            berth_id INT PRIMARY KEY
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
        '''CREATE TABLE IF NOT EXISTS ship_schedule (
            schedule_id SERIAL PRIMARY KEY,
            ship_mmsi INT NOT NULL,
            berth_id INT NOT NULL,
            e_arrival TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            e_departure TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            a_arrival TIMESTAMP WITHOUT TIME ZONE,
            a_departure TIMESTAMP WITHOUT TIME ZONE,
            FOREIGN KEY (ship_mmsi) REFERENCES ship(mmsi),
            FOREIGN KEY (berth_id) REFERENCES berth(berth_id),
            CHECK (e_arrival < e_departure AND a_arrival < a_departure)
        );'''
    ))
    db.execute(text(
        '''CREATE TABLE IF NOT EXISTS movement (
            movement_id SERIAL PRIMARY KEY,
            container_iso_id VARCHAR(11) NOT NULL,
            type VARCHAR(10) NOT NULL CHECK (type IN ('Unload', 'Transfer', 'Load')),
            e_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            e_end TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            a_start TIMESTAMP WITHOUT TIME ZONE,
            a_end TIMESTAMP WITHOUT TIME ZONE,
            ship_mmsi INT,
            src_bay INT,
            src_row INT,
            src_tier INT,
            des_bay INT,
            des_row INT,
            des_tier INT,
            FOREIGN KEY (container_iso_id) REFERENCES container(iso_id),
            FOREIGN KEY (ship_mmsi) REFERENCES ship(mmsi),
            FOREIGN KEY (src_bay, src_row, src_tier) REFERENCES yard_location(bay, row, tier),
            FOREIGN KEY (des_bay, des_row, des_tier) REFERENCES yard_location(bay, row, tier),
            CHECK (e_start < e_end AND a_start < a_end)
        );'''
    ))
    db.execute(text(
        '''
            -- PREVENTS SCHEDULE EVENT FROM BEING CREATED IF THERE IS AN OVERLAP IN TIMING
            -- WITH ANOTHER SCHEDULE OF THE SAME SHIP
            CREATE OR REPLACE FUNCTION prevent_schedule_time_conflict_func()
            RETURNS TRIGGER AS $$
            DECLARE
                conflict_count INT;
            BEGIN
                -- Check for time overlap conflicts
                SELECT COUNT(*)
                INTO conflict_count
                FROM ship_schedule
                WHERE ship_mmsi = NEW.ship_mmsi
                AND ((NEW.e_arrival BETWEEN e_arrival AND e_departure)
                OR (NEW.e_departure BETWEEN e_arrival AND e_departure));

                IF conflict_count > 0 THEN
                    RAISE EXCEPTION 'Time schedule conflict for ship % at %', NEW.ship_mmsi, NEW.e_start;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER prevent_schedule_time_conflict
            BEFORE INSERT ON ship_schedule
            FOR EACH ROW
            EXECUTE FUNCTION prevent_schedule_time_conflict_func();

            -- PREVENTS MOVEMENT EVENT FROM BEING CREATED IF THERE IS AN OVERLAP IN TIMING
            -- WITH ANOTHER MOVEMENT OF THE SAME CONTAINER
            CREATE OR REPLACE FUNCTION prevent_movement_time_conflict_func()
            RETURNS TRIGGER AS $$
            DECLARE
                conflict_count INT;
            BEGIN
                -- Check for time overlap conflicts
                SELECT COUNT(*)
                INTO conflict_count
                FROM movement
                WHERE container_iso_id = NEW.container_iso_id
                AND ((NEW.e_start BETWEEN e_start AND e_end)
                OR (NEW.e_end BETWEEN e_start AND e_end));

                IF conflict_count > 0 THEN
                    RAISE EXCEPTION 'Time schedule conflict for container % for %', NEW.container_iso_id, NEW.e_start;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER prevent_movement_time_conflict
            BEFORE INSERT ON movement
            FOR EACH ROW
            EXECUTE FUNCTION prevent_movement_time_conflict_func();

            -- PREVENTS MOVEMENT EVENT FROM BEING CREATED IF LAST KNOWN 
            -- OPERATION OF THE CONTAINER IS A LOAD OPERATION
            CREATE OR REPLACE FUNCTION check_last_operation_not_load_func()
            RETURNS TRIGGER AS $$
            DECLARE
                last_movement_type VARCHAR(10);
            BEGIN
                -- Check the last movement operation type for the container
                SELECT type 
                INTO last_movement_type
                FROM movement
                WHERE container_iso_id = NEW.container_iso_id
                AND (NEW.e_start >= e_end OR
                    NEW.e_start >= a_end)
                ORDER BY a_end DESC
                LIMIT 1;
                -- If the last operation was 'Load', raise an exception
                IF last_movement_type = 'Load' THEN
                    RAISE EXCEPTION 'Container % was already loaded. Cannot insert new operation.', NEW.container_iso_id;
                END IF;

                -- If the check passes, allow the insert to proceed
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER check_last_operation_not_load
            BEFORE INSERT ON movement
            FOR EACH ROW
            EXECUTE FUNCTION check_last_operation_not_load_func();

            -- PREVENTS MOVEMENT EVENT FROM BEING CREATED IF THE SHIP WHICH CONTAINER IS 
            -- UNLOADED FROM/LOADED TO IS NOT AT BERTH
            CREATE OR REPLACE FUNCTION check_ship_at_berth_during_schedule()
            RETURNS TRIGGER AS $$
            DECLARE
                schedule_count INT;
            BEGIN
                -- Check if the ship is scheduled to be at the berth during the movement operation
                SELECT COUNT(*)
                INTO schedule_count
                FROM ship_schedule
                WHERE ship_mmsi = NEW.ship_mmsi
                AND (NEW.e_start >= e_arrival
                OR NEW.e_start >= a_arrival)
                AND NEW.e_end <= e_departure;

                -- If no schedule matches, raise an exception
                IF schedule_count = 0 THEN
                    RAISE EXCEPTION 'Ship % not scheduled at the berth during the expected time of operation (% to %). Unable to add operation for %.', 
                    NEW.ship_mmsi, NEW.e_start, NEW.e_end, NEW.container_iso_id;
                END IF;

                -- If the check passes, allow the insert to proceed
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER check_ship_at_berth_schedule
            BEFORE INSERT OR UPDATE ON movement
            FOR EACH ROW
            WHEN (NEW.type = 'Load' OR NEW.type = 'Unload')
            EXECUTE FUNCTION check_ship_at_berth_during_schedule();

            -- PREVENTS MOVEMENT EVENT FROM BEING UPDATED IF THE SHIP WHICH CONTAINER IS 
            -- UNLOADED FROM/LOADED TO IS NOT AT BERTH
            CREATE OR REPLACE FUNCTION check_ship_at_berth_during_operation()
            RETURNS TRIGGER AS $$
            DECLARE
                at_berth_count INT;
            BEGIN
                -- Check if the ship is at the berth (actual start time set, but no actual end time)
                SELECT COUNT(*)
                INTO at_berth_count
                FROM ship_schedule
                WHERE ship_mmsi = NEW.ship_mmsi
                AND NEW.a_end IS NOT NULL
                AND NEW.a_start >= a_arrival
                AND (NEW.a_end IS NULL OR NEW.a_end <= a_departure)
                AND a_end IS NULL;

                -- If no such schedule exists, raise an exception
                IF at_berth_count = 0 THEN
                    RAISE EXCEPTION 'Ship % not scheduled at the berth during the expected time of operation (% to %). Unable to add operation for %.', 
                    NEW.ship_mmsi, NEW.e_start, NEW.e_end, NEW.container_iso_id;
                END IF;

                -- If the check passes, allow the insert to proceed
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER check_ship_at_berth_operation
            BEFORE UPDATE ON movement
            FOR EACH ROW
            WHEN (NEW.type = 'Load' OR NEW.type = 'Unload')
            EXECUTE FUNCTION check_ship_at_berth_during_operation();

            -- PREVENTS UNLOAD EVENT FROM BEING CREATED IF THE YARD LOCATION IS TAKEN AT TIME OF OPERATION
            CREATE OR REPLACE FUNCTION check_yard_location_avaiable_func()
            RETURNS TRIGGER AS $$
            DECLARE
                location_is_available INT;
            BEGIN
                SELECT COUNT(*)
                INTO location_is_available
                FROM (
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
                        AND (m.a_end <= '2024-04-09 08:15:00' OR m.e_end <= '2024-04-09 08:15:00')
                        GROUP BY (y.bay, y.row, y.tier)
                    ) l1
                    WHERE (m1.a_end = l1.latest OR m1.e_end = l1.latest)
                    AND m1.des_bay=l1.bay AND m1.des_row=l1.row AND m1.des_tier=l1.tier
                    AND (m1.type = 'Unload' OR m1.type = 'Transfer')
                ) t
                WHERE t.bay=NEW.des_bay AND t.row=NEW.des_row AND t.row=NEW.des_row;
                
                -- If there are, raise an exception
                IF location_is_available = 0 THEN
                    RAISE EXCEPTION 'Yard location is not available at start time of operation (%). Unable to insert movement for container %.', 
                    NEW.e_start, NEW.container_iso_id;
                END IF;

                -- If the check passes, allow the insert to proceed
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER check_yard_location_avaiable
            BEFORE INSERT OR UPDATE ON movement
            FOR EACH ROW
            WHEN (NEW.type = 'Unload')
            EXECUTE FUNCTION check_yard_location_avaiable_func();

            -- PREVENTS TRANSFER/LOAD EVENT FROM BEING CREATED IF THE CONTAINER IS NOT AT THE SPECIFIED YARD LOCATION
            CREATE OR REPLACE FUNCTION check_container_at_correct_location_during_operation_func()
            RETURNS TRIGGER AS $$
            DECLARE
                container_at_location VARCHAR(11);
            BEGIN
                -- Check if the container is at the yard location during operation time
                SELECT container_iso_id
                INTO container_at_location
                FROM movement
                WHERE (NEW.e_start >= e_end 
                    OR NEW.e_start >= a_end)
                AND des_bay = NEW.src_bay
                AND des_row = NEW.src_row
                AND des_tier = NEW.src_tier
                ORDER BY e_end DESC
                LIMIT 1;
                
                -- If containers do not match, raise an exception
                IF container_at_location <> NEW.container_iso_id THEN
                    RAISE EXCEPTION 'Container % is not at the expected yard location at start time of operation (%).', 
                    NEW.container_iso_id, NEW.e_start;
                END IF;

                -- If the check passes, allow the insert to proceed
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER check_container_at_correct_location_during_operation
            BEFORE INSERT OR UPDATE ON movement
            FOR EACH ROW
            WHEN (NEW.type = 'Transfer' OR NEW.type = 'Load')
            EXECUTE FUNCTION check_container_at_correct_location_during_operation_func()
        ;'''
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
    #db.execute(text("".join(open("sql_data/movements.sql", "r").readlines())))
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
