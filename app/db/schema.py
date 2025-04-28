# SQL statements for creating business database tables
BUSINESS_DB_TABLES = {
    # These are already created in your existing setup
    # Just documenting them here for reference
    "agencies": """
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
    """,
    
    "agents": """
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
    """,
    
    # Additional existing tables would be defined here
}

# SQL statements for creating application database tables
APPLICATION_DB_TABLES = {
    "conversations": """
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'active'
        )
    """,
    
    "messages": """
        CREATE TABLE IF NOT EXISTS messages (
            message_id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB
        )
    """,
    
    "query_executions": """
        CREATE TABLE IF NOT EXISTS query_executions (
            execution_id VARCHAR(36) PRIMARY KEY,
            message_id VARCHAR(36) REFERENCES messages(message_id) ON DELETE CASCADE,
            sql_query TEXT NOT NULL,
            status VARCHAR(20) NOT NULL,
            execution_time_ms INTEGER,
            row_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error_message TEXT
        )
    """,
    
    "visualizations": """
        CREATE TABLE IF NOT EXISTS visualizations (
            visualization_id VARCHAR(36) PRIMARY KEY,
            message_id VARCHAR(36) REFERENCES messages(message_id) ON DELETE CASCADE,
            visualization_type VARCHAR(50) NOT NULL,
            configuration JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    # This will be populated in the next phase
    "vector_embeddings": """
        CREATE TABLE IF NOT EXISTS vector_embeddings (
            embedding_id VARCHAR(36) PRIMARY KEY,
            content_type VARCHAR(50) NOT NULL,
            content_id VARCHAR(36) NOT NULL,
            embedding_data BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB
        )
    """
}

# SQL statements for creating business database indexes
BUSINESS_DB_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_policies_status ON policies(status)",
    "CREATE INDEX IF NOT EXISTS idx_policies_policy_type ON policies(policy_type)",
    "CREATE INDEX IF NOT EXISTS idx_policies_start_date ON policies(start_date)",
    "CREATE INDEX IF NOT EXISTS idx_claims_claim_status ON claims(claim_status)",
    "CREATE INDEX IF NOT EXISTS idx_claims_claim_type ON claims(claim_type)",
    "CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)",
    "CREATE INDEX IF NOT EXISTS idx_agencies_region ON agencies(region)",
]

# SQL statements for creating application database indexes
APPLICATION_DB_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_query_executions_message_id ON query_executions(message_id)",
    "CREATE INDEX IF NOT EXISTS idx_visualizations_message_id ON visualizations(message_id)",
    "CREATE INDEX IF NOT EXISTS idx_vector_embeddings_content_id ON vector_embeddings(content_id)",
    "CREATE INDEX IF NOT EXISTS idx_vector_embeddings_content_type ON vector_embeddings(content_type)",
]