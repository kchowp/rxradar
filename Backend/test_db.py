# test_db.py
import os
import time
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError

# We need to import the Base from your models file
from db import Base 
import Backend.models as models # Make sure all models are imported so Base knows about them

def run_test():
    """
    A simple, direct test to connect to the database and create tables.
    """
    print("--- Starting Database Table Creation Test ---")
    
    # Get the database URL from the environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        return

    print(f"Connecting to database at: {db_url}")

    # Retry loop to wait for the database to be ready
    for i in range(10): # Try for 10 seconds
        try:
            engine = create_engine(db_url)
            # The 'connect()' method will raise an error if the DB is not ready
            connection = engine.connect() 
            print("--> Connection Successful!")
            break
        except OperationalError:
            print(f"Attempt {i+1}: Database not ready, waiting 1 second...")
            time.sleep(1)
    else:
        print("--> FAILED: Could not connect to the database after 10 seconds.")
        return

    # Now, create the tables
    try:
        print("Attempting to create all tables...")
        # This line tells SQLAlchemy to create all tables that inherit from Base
        Base.metadata.create_all(bind=engine)
        print("--> Table creation command executed successfully.")
    except Exception as e:
        print(f"--> FAILED: An error occurred during table creation: {e}")
        return

    # Finally, verify that the tables were actually created
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print("\nVerification Step: Checking for tables in the database...")
        if tables:
            print("--> SUCCESS! Found the following tables:")
            for table in tables:
                print(f"    - {table}")
        else:
            print("--> FAILED: No tables were found in the database after creation.")
    except Exception as e:
        print(f"--> FAILED: An error occurred during verification: {e}")
    
    print("\n--- Test Complete ---")
    connection.close()


if __name__ == "__main__":
    run_test()