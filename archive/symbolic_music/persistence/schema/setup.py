"""
Initialize Memgraph with schema constraints and indexes.
"""

import os

from gqlalchemy import Memgraph


def setup_schema(host: str = "127.0.0.1", port: int = 7687):
    """Execute schema setup from cypher file."""
    db = Memgraph(host=host, port=port)
    
    print("🔧 Setting up Memgraph schema...")
    
    # Read schema file
    schema_dir = os.path.dirname(os.path.abspath(__file__))
    cypher_path = os.path.join(schema_dir, "schema.cypher")
    
    with open(cypher_path, "r") as f:
        content = f.read()
    
    # Parse commands
    commands = []
    for cmd in content.split(";"):
        cmd = cmd.strip()
        lines = [l for l in cmd.split("\n") if l.strip() and not l.strip().startswith("//")]
        if lines:
            commands.append("\n".join(lines))
    
    # Execute each command
    for cmd in commands:
        try:
            list(db.execute_and_fetch(cmd))
            print(f"✅ {cmd[:60]}...")
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" in err_str or "equivalent" in err_str:
                print(f"⚠️  Already exists: {cmd[:50]}...")
            else:
                print(f"❌ Error: {e}")
    
    print("\n🎯 Schema setup complete!")
    print("Database ready for data.")


if __name__ == "__main__":
    setup_schema()
