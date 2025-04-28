import psycopg2
import pandas as pd
import os
from io import StringIO

# PostgreSQL connection parameters
DB_CONFIG = {
    "dbname": "postgres",  # Connect to default postgres database first
    "user": "postgres",
    "password": "",  # Replace with your password
    "host": "localhost",
    "port": "5432"
}

# Create the insurance_db database
def create_database():
    # Connect to default database
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Check if database exists
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'insurance_db'")
    exists = cursor.fetchone()
    
    if not exists:
        print("Creating insurance_db database...")
        cursor.execute("CREATE DATABASE insurance_db")
        print("Database created successfully!")
    else:
        print("Database insurance_db already exists.")
    
    cursor.close()
    conn.close()

# Create tables in the insurance_db
def create_tables():
    # Connect to insurance_db
    config = DB_CONFIG.copy()
    config["dbname"] = "insurance_db"
    conn = psycopg2.connect(**config)
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Create tables
    print("Creating tables...")
    
    # Agencies table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agencies (
        agency_id SERIAL PRIMARY KEY,
        agency_name VARCHAR(100) NOT NULL,
        address VARCHAR(200),
        city VARCHAR(50),
        state VARCHAR(2),
        zip_code VARCHAR(10),
        establishment_date DATE,
        region VARCHAR(20),
        tier VARCHAR(10)
    )
    """)
    
    # Agents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        agent_id SERIAL PRIMARY KEY,
        agency_id INTEGER REFERENCES agencies(agency_id),
        agent_name VARCHAR(100) NOT NULL,
        hire_date DATE,
        status VARCHAR(20) DEFAULT 'active',
        email VARCHAR(100),
        experience_years INTEGER,
        certification_level VARCHAR(20)
    )
    """)
    
    # Distribution Channels table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS distribution_channels (
        channel_id SERIAL PRIMARY KEY,
        channel_name VARCHAR(100) NOT NULL,
        channel_type VARCHAR(50) NOT NULL,
        commission_rate DECIMAL(5,2)
    )
    """)
    
    # Customers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id SERIAL PRIMARY KEY,
        customer_name VARCHAR(100) NOT NULL,
        customer_type VARCHAR(20), 
        address VARCHAR(200),
        city VARCHAR(50),
        state VARCHAR(2),
        zip_code VARCHAR(10),
        registration_date DATE
    )
    """)
    
    # Policies table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS policies (
        policy_id SERIAL PRIMARY KEY,
        policy_number VARCHAR(50) UNIQUE NOT NULL,
        customer_id INTEGER REFERENCES customers(customer_id),
        agent_id INTEGER REFERENCES agents(agent_id),
        channel_id INTEGER REFERENCES distribution_channels(channel_id),
        policy_type VARCHAR(50) NOT NULL,
        start_date DATE,
        end_date DATE,
        premium_amount DECIMAL(12,2),
        status VARCHAR(20),
        annual_revenue_impact DECIMAL(12,2),
        risk_score INTEGER
    )
    """)
    
    # Claims table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        claim_id SERIAL PRIMARY KEY,
        policy_id INTEGER REFERENCES policies(policy_id),
        claim_date DATE,
        claim_amount DECIMAL(12,2),
        claim_status VARCHAR(20),
        claim_type VARCHAR(50),
        settlement_date DATE,
        deductible_amount DECIMAL(10,2)
    )
    """)
    
    print("Tables created successfully!")
    cursor.close()
    conn.close()

# Load data from CSV files
def load_data():
    # Connect to insurance_db
    config = DB_CONFIG.copy()
    config["dbname"] = "insurance_db"
    conn = psycopg2.connect(**config)
    cursor = conn.cursor()
    
    # Load data from CSV files
    tables = [
        "agencies",
        "agents",
        "distribution_channels",
        "customers",
        "policies",
        "claims"
    ]
    
    for table in tables:
        csv_file = f"data/{table}.csv"
        
        if os.path.exists(csv_file):
            print(f"Loading data into {table} table...")
            
            # Read CSV file
            df = pd.read_csv(csv_file)
            
            # Create a string buffer
            buffer = StringIO()
            df.to_csv(buffer, index=False, header=False)
            buffer.seek(0)
            
            # Use COPY command to bulk insert
            cursor.copy_expert(f"COPY {table} FROM STDIN WITH CSV", buffer)
            conn.commit()
            
            print(f"Loaded {len(df)} rows into {table} table.")
        else:
            print(f"Warning: {csv_file} not found!")
    
    cursor.close()
    conn.close()

# Create indexes for better performance
def create_indexes():
    # Connect to insurance_db
    config = DB_CONFIG.copy()
    config["dbname"] = "insurance_db"
    conn = psycopg2.connect(**config)
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("Creating indexes...")
    
    # Indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_policies_status ON policies(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_policies_policy_type ON policies(policy_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_policies_start_date ON policies(start_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_claim_status ON claims(claim_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_claim_type ON claims(claim_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_region ON agencies(region)")
    
    print("Indexes created successfully!")
    cursor.close()
    conn.close()

# Main function to set up the database
def main():
    print("Setting up insurance database...")
    
    # Create database
    create_database()
    
    # Create tables
    create_tables()
    
    # Load data
    load_data()
    
    # Create indexes
    create_indexes()
    
    print("Database setup completed successfully!")

if __name__ == "__main__":
    main()