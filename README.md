# Container_Terminal_Operation

This is a project that builds a database for a ship company. It records the scheduling and recording of ships and containers.

1. Install packages
  ```sh
  pip install -r requirements.txt
  ```

2. Open PostgreSQL PGadmin4, creat a database named Project.

3. Replace the following with your actual connection details in db_manager.py.
 ```username = 'postgres'
password = '000000'
hostname = 'localhost:5432'
database_name = 'Project'
 ```

4. Start app
  ```sh
  python3 app.py
 ```
Edit based on: https://github.com/HiIAmTzeKean/IT2002-Database-Technology-and-Management