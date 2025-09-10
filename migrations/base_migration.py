# ================================
# File: migrations/base_migration.py
# ================================
"""
Base migration class for MongoDB migrations
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Custom exception for migration errors"""
    pass


class BaseMigration(ABC):
    """Abstract base class for all migrations"""
    
    def __init__(self, connection_string: Optional[str] = None, db_name: Optional[str] = None):
        self.connection_string = connection_string or os.getenv(
            'MONGODB_URI', 
            'mongodb://localhost:27017'
        )
        self.db_name = db_name or os.getenv('DATABASE_NAME', 'healthcare')
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        
    def connect(self) -> None:
        """Establish database connection"""
        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.db_name]
            # Test connection
            self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {self.db_name}")
        except Exception as e:
            raise MigrationError(f"Failed to connect to MongoDB: {str(e)}")
    
    def disconnect(self) -> None:
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    @abstractmethod
    def up(self) -> None:
        """Apply the migration"""
        pass
    
    @abstractmethod
    def down(self) -> None:
        """Rollback the migration"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Migration version identifier"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Migration description"""
        pass


# ================================
# File: migrations/versions/__init__.py
# ================================
"""
Migration versions package
"""

# ================================
# File: migrations/versions/001_create_homecare_collection.py
# ================================
"""
Migration: Create homecare collection with schema validation
Version: 001
"""

from datetime import datetime
from typing import Dict
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import CollectionInvalid, OperationFailure

from ..base_migration import BaseMigration, MigrationError
import logging

logger = logging.getLogger(__name__)


class CreateHomecareCollectionMigration(BaseMigration):
    """Migration to create homecare collection with schema validation"""
    
    @property
    def version(self) -> str:
        return "001"
    
    @property
    def description(self) -> str:
        return "Create homecare collection with schema validation and indexes"
    
    def get_schema_validator(self) -> Dict:
        """Return the JSON schema validator for homecare collection"""
        return {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["patient_state"],
                "additionalProperties": False,
                "properties": {
                    "_id": {
                        "bsonType": "objectId"
                    },
                    "patient_state": {
                        "bsonType": "string",
                        "description": "Current state of the patient - required field"
                    },
                    "vitals": {
                        "bsonType": "object",
                        "additionalProperties": False,
                        "properties": {
                            "bp_systolic": {
                                "bsonType": "int",
                                "minimum": 0,
                                "maximum": 300,
                                "description": "Systolic blood pressure in mmHg"
                            },
                            "bp_diastolic": {
                                "bsonType": "int", 
                                "minimum": 0,
                                "maximum": 200,
                                "description": "Diastolic blood pressure in mmHg"
                            },
                            "hr": {
                                "bsonType": "int",
                                "minimum": 0,
                                "maximum": 250,
                                "description": "Heart rate in beats per minute"
                            },
                            "temp_c": {
                                "bsonType": "number",
                                "minimum": 25.0,
                                "maximum": 50.0,
                                "description": "Temperature in Celsius"
                            },
                            "spo2": {
                                "bsonType": "int",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Blood oxygen saturation percentage"
                            }
                        }
                    },
                    "medications_in_use": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "string"
                        },
                        "description": "Array of current medications patient is using"
                    },
                    "medications_administered": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "required": ["name", "dose", "route", "time"],
                            "additionalProperties": False,
                            "properties": {
                                "name": {
                                    "bsonType": "string",
                                    "description": "Medication name"
                                },
                                "dose": {
                                    "bsonType": "string",
                                    "description": "Medication dosage"
                                },
                                "route": {
                                    "bsonType": "string",
                                    "description": "Route of administration"
                                },
                                "time": {
                                    "bsonType": "date",
                                    "description": "Time when medication was administered"
                                }
                            }
                        },
                        "description": "Array of medications administered during this visit"
                    },
                    "materials_used": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "string"
                        },
                        "description": "Array of materials/supplies used"
                    },
                    "interventions": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "string"
                        },
                        "description": "Array of interventions performed"
                    },
                    "recommendations": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "string"
                        },
                        "description": "Array of recommendations for patient care"
                    },
                    "observations": {
                        "bsonType": "string",
                        "description": "General observations about the patient"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "Record creation timestamp"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "Record last update timestamp"
                    }
                }
            }
        }
    
    def create_indexes(self, collection: Collection) -> None:
        """Create indexes for the homecare collection"""
        indexes = [
            {
                "keys": [("patient_state", ASCENDING)],
                "name": "idx_patient_state"
            },
            {
                "keys": [("created_at", DESCENDING)],
                "name": "idx_created_at_desc"
            },
            {
                "keys": [
                    ("medications_administered.time", DESCENDING),
                    ("medications_administered.name", ASCENDING)
                ],
                "name": "idx_medications_time_name"
            },
            {
                "keys": [
                    ("vitals.bp_systolic", ASCENDING),
                    ("vitals.bp_diastolic", ASCENDING)
                ],
                "name": "idx_blood_pressure"
            },
            {
                "keys": [("updated_at", DESCENDING)],
                "name": "idx_updated_at_desc"
            }
        ]
        
        for index_spec in indexes:
            try:
                collection.create_index(
                    index_spec["keys"],
                    name=index_spec["name"]
                )
                logger.info(f"Created index: {index_spec['name']}")
            except OperationFailure as e:
                if "already exists" in str(e):
                    logger.info(f"Index {index_spec['name']} already exists, skipping")
                else:
                    raise MigrationError(f"Failed to create index {index_spec['name']}: {str(e)}")
    
    def up(self) -> None:
        """Apply the migration - create collection with validation and indexes"""
        if not self.client:
            self.connect()
        
        try:
            collection_name = "homecare"
            logger.info(f"Starting migration up for {collection_name} collection...")
            
            # Check if collection already exists
            if collection_name in self.db.list_collection_names():
                logger.warning(f"Collection {collection_name} already exists")
                return
            
            # Create collection with schema validation
            self.db.create_collection(
                collection_name,
                validator=self.get_schema_validator(),
                validationLevel="strict",
                validationAction="error"
            )
            
            logger.info(f"Created {collection_name} collection with schema validation")
            
            # Get the collection and create indexes
            collection = self.db[collection_name]
            self.create_indexes(collection)
            
            logger.info(f"Migration up completed successfully for {collection_name}")
            
        except CollectionInvalid as e:
            raise MigrationError(f"Failed to create collection: {str(e)}")
        except Exception as e:
            raise MigrationError(f"Migration up failed: {str(e)}")
    
    def down(self) -> None:
        """Rollback the migration - drop the collection"""
        if not self.client:
            self.connect()
        
        try:
            collection_name = "homecare"
            logger.info(f"Starting migration down for {collection_name} collection...")
            
            # Check if collection exists
            if collection_name not in self.db.list_collection_names():
                logger.warning(f"Collection {collection_name} does not exist")
                return
            
            # Drop the collection
            self.db.drop_collection(collection_name)
            logger.info(f"Dropped {collection_name} collection")
            
            logger.info(f"Migration down completed successfully for {collection_name}")
            
        except Exception as e:
            raise MigrationError(f"Migration down failed: {str(e)}")


# ================================
# File: migrations/migration_runner.py
# ================================
"""
Migration runner for managing MongoDB migrations
"""

import os
import sys
import importlib
import logging
from datetime import datetime
from typing import List, Dict, Optional, Type
from pymongo import MongoClient
from pymongo.database import Database

from .base_migration import BaseMigration, MigrationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Manages and executes MongoDB migrations"""
    
    def __init__(self, connection_string: Optional[str] = None, db_name: Optional[str] = None):
        self.connection_string = connection_string or os.getenv(
            'MONGODB_URI', 
            'mongodb://localhost:27017'
        )
        self.db_name = db_name or os.getenv('DATABASE_NAME', 'healthcare')
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.migrations_collection = "_migrations"
        
    def connect(self) -> None:
        """Establish database connection"""
        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.db_name]
            self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {self.db_name}")
        except Exception as e:
            raise MigrationError(f"Failed to connect to MongoDB: {str(e)}")
    
    def disconnect(self) -> None:
        """Close database connection"""
        if self.client:
            self.client.close()
    
    def get_migration_classes(self) -> List[Type[BaseMigration]]:
        """Discover and load all migration classes"""
        migrations = []
        migrations_dir = os.path.join(os.path.dirname(__file__), 'versions')
        
        # Get all Python files in versions directory
        for filename in sorted(os.listdir(migrations_dir)):
            if filename.startswith('__') or not filename.endswith('.py'):
                continue
                
            module_name = filename[:-3]  # Remove .py extension
            
            try:
                # Import the module
                module = importlib.import_module(f'.versions.{module_name}', package='migrations')
                
                # Find migration classes in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseMigration) and 
                        attr != BaseMigration):
                        migrations.append(attr)
                        break
                        
            except ImportError as e:
                logger.warning(f"Failed to import migration {module_name}: {e}")
                continue
        
        # Sort by version
        migrations.sort(key=lambda cls: cls().version)
        return migrations
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions"""
        if not self.client:
            self.connect()
            
        try:
            collection = self.db[self.migrations_collection]
            applied = collection.find({}, {"version": 1}).sort("applied_at", 1)
            return [doc["version"] for doc in applied]
        except Exception:
            return []
    
    def mark_migration_applied(self, migration: BaseMigration) -> None:
        """Mark a migration as applied"""
        if not self.client:
            self.connect()
            
        collection = self.db[self.migrations_collection]
        collection.insert_one({
            "version": migration.version,
            "description": migration.description,
            "applied_at": datetime.utcnow()
        })
    
    def mark_migration_unapplied(self, migration: BaseMigration) -> None:
        """Mark a migration as unapplied (remove from applied list)"""
        if not self.client:
            self.connect()
            
        collection = self.db[self.migrations_collection]
        collection.delete_one({"version": migration.version})
    
    def migrate_up(self, target_version: Optional[str] = None) -> None:
        """Apply migrations up to target version (or all if None)"""
        migration_classes = self.get_migration_classes()
        applied_versions = self.get_applied_migrations()
        
        for migration_cls in migration_classes:
            migration = migration_cls(self.connection_string, self.db_name)
            
            # Skip if already applied
            if migration.version in applied_versions:
                continue
                
            # Stop if we've reached the target version
            if target_version and migration.version > target_version:
                break
                
            try:
                logger.info(f"Applying migration {migration.version}: {migration.description}")
                migration.up()
                self.mark_migration_applied(migration)
                logger.info(f"Successfully applied migration {migration.version}")
            except Exception as e:
                logger.error(f"Failed to apply migration {migration.version}: {e}")
                raise
            finally:
                migration.disconnect()
    
    def migrate_down(self, target_version: Optional[str] = None) -> None:
        """Rollback migrations down to target version"""
        migration_classes = self.get_migration_classes()
        applied_versions = self.get_applied_migrations()
        
        # Reverse order for rollbacks
        for migration_cls in reversed(migration_classes):
            migration = migration_cls(self.connection_string, self.db_name)
            
            # Skip if not applied
            if migration.version not in applied_versions:
                continue
                
            # Stop if we've reached the target version
            if target_version and migration.version <= target_version:
                break
                
            try:
                logger.info(f"Rolling back migration {migration.version}: {migration.description}")
                migration.down()
                self.mark_migration_unapplied(migration)
                logger.info(f"Successfully rolled back migration {migration.version}")
            except Exception as e:
                logger.error(f"Failed to rollback migration {migration.version}: {e}")
                raise
            finally:
                migration.disconnect()
    
    def show_status(self) -> None:
        """Show migration status"""
        migration_classes = self.get_migration_classes()
        applied_versions = self.get_applied_migrations()
        
        print("\nMigration Status:")
        print("-" * 70)
        print(f"{'Version':<10} {'Status':<10} {'Description'}")
        print("-" * 70)
        
        for migration_cls in migration_classes:
            migration = migration_cls()
            status = "Applied" if migration.version in applied_versions else "Pending"
            print(f"{migration.version:<10} {status:<10} {migration.description}")
        
        print("-" * 70)
        print(f"Database: {self.db_name}")
        print(f"Applied migrations: {len(applied_versions)}")
        print(f"Pending migrations: {len(migration_classes) - len(applied_versions)}")


def main():
    """CLI interface for migration runner"""
    if len(sys.argv) < 2:
        print("Usage: python -m migrations.migration_runner [up|down|status] [version]")
        print("  up     - Apply pending migrations")
        print("  down   - Rollback migrations")
        print("  status - Show migration status")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    target_version = sys.argv[2] if len(sys.argv) > 2 else None
    
    runner = MigrationRunner()
    
    try:
        if action == "up":
            runner.migrate_up(target_version)
            print("Migrations completed successfully")
        elif action == "down":
            runner.migrate_down(target_version)
            print("Rollback completed successfully")
        elif action == "status":
            runner.show_status()
        else:
            print("Invalid action. Use 'up', 'down', or 'status'")
            sys.exit(1)
    
    except MigrationError as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        runner.disconnect()


if __name__ == "__main__":
    main()


# ================================
# File: migrations/utils.py
# ================================
"""
Utility functions for migrations
"""

from datetime import datetime
from typing import Dict


def get_sample_homecare_document() -> Dict:
    """Get a sample homecare document for testing"""
    return {
        "patient_state": "stable",
        "vitals": {
            "bp_systolic": 120,
            "bp_diastolic": 80,
            "hr": 72,
            "temp_c": 36.5,
            "spo2": 98
        },
        "medications_in_use": ["Lisinopril", "Metformin"],
        "medications_administered": [
            {
                "name": "Insulin",
                "dose": "10 units", 
                "route": "subcutaneous",
                "time": datetime.utcnow()
            }
        ],
        "materials_used": ["Glucose strips", "Insulin syringe"],
        "interventions": ["Blood glucose monitoring", "Insulin administration"],
        "recommendations": [
            "Continue current medication regimen",
            "Monitor blood glucose twice daily"
        ],
        "observations": "Patient appears comfortable and cooperative",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }


def validate_homecare_document(document: Dict) -> bool:
    """Basic validation for homecare documents"""
    required_fields = ["patient_state"]
    
    for field in required_fields:
        if field not in document:
            return False
    
    # Validate vitals if present
    if "vitals" in document:
        vitals = document["vitals"]
        if "bp_systolic" in vitals and not (0 <= vitals["bp_systolic"] <= 300):
            return False
        if "bp_diastolic" in vitals and not (0 <= vitals["bp_diastolic"] <= 200):
            return False
        if "hr" in vitals and not (0 <= vitals["hr"] <= 250):
            return False
        if "temp_c" in vitals and not (25 <= vitals["temp_c"] <= 50):
            return False
        if "spo2" in vitals and not (0 <= vitals["spo2"] <= 100):
            return False
    
    return True