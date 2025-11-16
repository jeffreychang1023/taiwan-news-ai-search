#!/usr/bin/env python3
"""
Clear all test data from analytics database.
Use with caution - this will delete ALL data!
"""

import os
import sys
sys.path.insert(0, 'code/python')
from core.analytics_db import AnalyticsDB

def clear_analytics_data():
    """Clear all data from analytics tables."""

    # Get database URL from environment
    db_url = os.environ.get('ANALYTICS_DATABASE_URL')

    if not db_url:
        print("ERROR: ANALYTICS_DATABASE_URL environment variable not set")
        print("Using default database path...")
        db = AnalyticsDB()
    else:
        print(f"Connecting to Neon PostgreSQL database...")
        db = AnalyticsDB(db_url)

    try:
        # Connect to database
        conn = db.connect()
        cursor = conn.cursor()

        # Delete in correct order (respecting foreign keys)
        # Whitelist of allowed tables to prevent SQL injection
        ALLOWED_TABLES = {
            'user_interactions',
            'ranking_scores',
            'retrieved_documents',
            'feature_vectors',
            'queries'
        }

        tables = [
            'user_interactions',
            'ranking_scores',
            'retrieved_documents',
            'feature_vectors',
            'queries'
        ]

        for table in tables:
            # Validate table name against whitelist
            if table not in ALLOWED_TABLES:
                print(f"⚠️ Skipping invalid table: {table}")
                continue

            print(f"Clearing table: {table}...", end=' ')
            cursor.execute(f"DELETE FROM {table}")
            deleted = cursor.rowcount
            print(f"Deleted {deleted} rows")

        # Commit changes
        conn.commit()
        print("\n✅ All test data cleared successfully!")

        # Close connection
        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"\n❌ Error clearing data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("CLEAR ANALYTICS TEST DATA")
    print("=" * 60)
    print("\n⚠️  WARNING: This will delete ALL data from analytics tables!")
    print("Tables to be cleared:")
    print("  - user_interactions")
    print("  - ranking_scores")
    print("  - retrieved_documents")
    print("  - feature_vectors")
    print("  - queries")
    print()

    response = input("Are you sure you want to proceed? (yes/no): ")

    if response.lower() == 'yes':
        print("\nProceeding with data clear...\n")
        clear_analytics_data()
    else:
        print("\n❌ Operation cancelled.")
