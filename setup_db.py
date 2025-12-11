#!/usr/bin/env python3
"""
MongoDB Database Setup Script for Telcenter Base Service
Creates the required databases and collections
"""

import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

def setup_databases():
    """Setup MongoDB databases and collections"""

    # Load environment variables
    load_dotenv()

    # Get MongoDB URIs from environment
    mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017/telcenter_core')
    partner_mongo_url = os.getenv('PARTNER_MONGODB_URI', 'mongodb://localhost:27017/telcenter_partner')

    print("🔧 Setting up Telcenter databases...")
    print(f"📍 Main DB: {mongo_url}")
    print(f"📍 Partner DB: {partner_mongo_url}")
    print()

    try:
        # Connect to main database
        print("🔌 Connecting to main database...")
        main_client = MongoClient(mongo_url)
        main_db = main_client.get_default_database()

        # Test connection
        main_client.admin.command('ping')
        print("✅ Main database connected successfully")

        # Create collections for main database
        collections_to_create = ['conversations', 'messages']

        for collection_name in collections_to_create:
            if collection_name not in main_db.list_collection_names():
                main_db.create_collection(collection_name)
                print(f"✅ Created collection: {collection_name}")
            else:
                print(f"ℹ️  Collection already exists: {collection_name}")

        # Connect to partner database
        print("\n🔌 Connecting to partner database...")
        partner_client = MongoClient(partner_mongo_url)
        partner_db = partner_client.get_default_database()

        # Test connection
        partner_client.admin.command('ping')
        print("✅ Partner database connected successfully")

        # Create collections for partner database
        partner_collections = ['customers']

        for collection_name in partner_collections:
            if collection_name not in partner_db.list_collection_names():
                partner_db.create_collection(collection_name)
                print(f"✅ Created collection: {collection_name}")
            else:
                print(f"ℹ️  Collection already exists: {collection_name}")

        # Create indexes for customers collection
        print("\n📊 Creating indexes...")
        customers_collection = partner_db.customers

        # Create unique index on email
        customers_collection.create_index("email", unique=True)
        print("✅ Created unique index on customers.email")

        print("\n🎉 Database setup completed successfully!")
        print("\n📋 Summary:")
        print(f"   - Main database: {main_db.name}")
        print(f"   - Collections: {', '.join(collections_to_create)}")
        print(f"   - Partner database: {partner_db.name}")
        print(f"   - Collections: {', '.join(partner_collections)}")
        print("   - Indexes: email (unique)")

    except ConnectionFailure as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        print("\n🔍 Troubleshooting:")
        print("   - Make sure MongoDB is running: mongod")
        print("   - Check connection string in .env file")
        print("   - Verify MongoDB service is started")
        return False

    except Exception as e:
        print(f"❌ Error during setup: {e}")
        return False

    finally:
        # Close connections
        try:
            main_client.close()
            partner_client.close()
        except:
            pass

    return True

if __name__ == "__main__":
    print("🚀 Telcenter Database Setup")
    print("=" * 40)

    success = setup_databases()

    if success:
        print("\n✅ Setup completed! You can now start the service.")
        print("   Run: python -m app")
        print("   Or: .\start.bat (Windows)")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        exit(1)