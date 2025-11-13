"""
Deploy Data Warehouse to Supabase
===================================
Exports MySQL Star Schema to Supabase Storage (Analytics Bucket)
- Extracts all tables from MySQL
- Converts to Parquet format for efficient analytics
- Uploads to Supabase storage buckets
- Creates metadata and documentation

Author: Muhammad Ali
Date: November 12, 2025
"""

import pymysql
import pandas as pd
import os
import json
from datetime import datetime
from supabase import create_client, Client
import pyarrow as pa
import pyarrow.parquet as pq
import warnings
warnings.filterwarnings('ignore')


class DataWarehouseDeployer:
    """
    Deploy MySQL Data Warehouse to Supabase Storage
    """
    
    def __init__(self, mysql_config, supabase_url, supabase_key):
        """Initialize with MySQL and Supabase configurations"""
        self.mysql_config = mysql_config
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.mysql_conn = None
        self.supabase_client = None
        self.export_dir = "./exports"
        self.deployment_log = []
        
    def connect_mysql(self):
        """Connect to MySQL database"""
        try:
            self.mysql_conn = pymysql.connect(**self.mysql_config)
            print("✅ Connected to MySQL database")
            return True
        except Exception as e:
            print(f"❌ MySQL connection error: {e}")
            return False
    
    def connect_supabase(self):
        """Connect to Supabase"""
        try:
            self.supabase_client = create_client(self.supabase_url, self.supabase_key)
            print("✅ Connected to Supabase")
            return True
        except Exception as e:
            print(f"❌ Supabase connection error: {e}")
            return False
    
    def close_mysql(self):
        """Close MySQL connection"""
        if self.mysql_conn:
            self.mysql_conn.close()
            print("✅ MySQL connection closed")
    
    def create_export_directory(self):
        """Create directory for exports"""
        try:
            os.makedirs(self.export_dir, exist_ok=True)
            os.makedirs(f"{self.export_dir}/parquet", exist_ok=True)
            os.makedirs(f"{self.export_dir}/csv", exist_ok=True)
            os.makedirs(f"{self.export_dir}/metadata", exist_ok=True)
            print(f"✅ Export directory created: {self.export_dir}")
            return True
        except Exception as e:
            print(f"❌ Error creating export directory: {e}")
            return False
    
    def get_all_tables(self):
        """Get list of all tables in the database"""
        try:
            query = f"SHOW TABLES FROM {self.mysql_config['database']}"
            cursor = self.mysql_conn.cursor()
            cursor.execute(query)
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            print(f"✅ Found {len(tables)} tables: {tables}")
            return tables
        except Exception as e:
            print(f"❌ Error getting tables: {e}")
            return []
    
    def export_table_to_parquet(self, table_name):
        """
        Export MySQL table to Parquet format
        Parquet is columnar and highly compressed - ideal for analytics
        """
        try:
            print(f"\n📊 Exporting table: {table_name}")
            
            # Read table from MySQL
            query = f"SELECT * FROM {table_name}"
            df = pd.read_sql(query, self.mysql_conn)
            
            row_count = len(df)
            print(f"   Records: {row_count:,}")
            print(f"   Columns: {len(df.columns)}")
            
            if row_count == 0:
                print(f"   ⚠️ Table is empty, skipping...")
                return None
            
            # Export to Parquet (compressed, columnar format)
            parquet_path = f"{self.export_dir}/parquet/{table_name}.parquet"
            df.to_parquet(parquet_path, engine='pyarrow', compression='snappy', index=False)
            
            # Also export to CSV for compatibility
            csv_path = f"{self.export_dir}/csv/{table_name}.csv"
            df.to_csv(csv_path, index=False)
            
            # Get file sizes
            parquet_size = os.path.getsize(parquet_path) / 1024  # KB
            csv_size = os.path.getsize(csv_path) / 1024  # KB
            compression_ratio = (1 - parquet_size/csv_size) * 100 if csv_size > 0 else 0
            
            print(f"   ✅ Parquet: {parquet_size:.2f} KB")
            print(f"   ✅ CSV: {csv_size:.2f} KB")
            print(f"   💾 Compression: {compression_ratio:.1f}% smaller")
            
            # Create metadata
            metadata = {
                'table_name': table_name,
                'row_count': row_count,
                'column_count': len(df.columns),
                'columns': df.columns.tolist(),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                'parquet_size_kb': round(parquet_size, 2),
                'csv_size_kb': round(csv_size, 2),
                'compression_ratio': round(compression_ratio, 1),
                'export_timestamp': datetime.now().isoformat(),
                'sample_data': df.head(3).to_dict('records')
            }
            
            # Save metadata
            metadata_path = f"{self.export_dir}/metadata/{table_name}_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=4, default=str)
            
            self.deployment_log.append({
                'table': table_name,
                'status': 'exported',
                'rows': row_count,
                'size_kb': parquet_size
            })
            
            return {
                'parquet_path': parquet_path,
                'csv_path': csv_path,
                'metadata_path': metadata_path,
                'metadata': metadata
            }
            
        except Exception as e:
            print(f"   ❌ Error exporting {table_name}: {e}")
            self.deployment_log.append({
                'table': table_name,
                'status': 'export_failed',
                'error': str(e)
            })
            return None
    
    def create_or_get_bucket(self, bucket_name='analytics-dwh'):
        """
        Create Supabase storage bucket if it doesn't exist
        """
        try:
            print(f"\n🪣 Checking bucket: {bucket_name}")
            
            # Try to test if bucket exists by attempting to list files in it
            # This works even with RLS when bucket is public
            try:
                # Try to list files in the bucket (will fail if bucket doesn't exist)
                self.supabase_client.storage.from_(bucket_name).list()
                print(f"   ✅ Bucket '{bucket_name}' exists and is accessible")
                return bucket_name
            except Exception as test_error:
                error_msg = str(test_error).lower()
                
                # Check if it's a "bucket not found" error vs other errors
                if 'not found' in error_msg or 'does not exist' in error_msg:
                    print(f"   ⚠️ Bucket '{bucket_name}' not found")
                    
                    # Try to create it
                    try:
                        self.supabase_client.storage.create_bucket(
                            bucket_name,
                            options={
                                "public": True,  # Public bucket to bypass RLS
                                "file_size_limit": 52428800,  # 50MB limit
                                "allowed_mime_types": ["text/csv", "application/octet-stream", "application/json", "application/x-parquet"]
                            }
                        )
                        print(f"   ✅ Bucket '{bucket_name}' created successfully")
                        return bucket_name
                    except Exception as create_error:
                        print(f"   ❌ Cannot create bucket: {create_error}")
                        print(f"\n   💡 MANUAL SETUP REQUIRED:")
                        print(f"   1. Go to: https://app.supabase.com/")
                        print(f"   2. Storage → New Bucket")
                        print(f"   3. Name: '{bucket_name}'")
                        print(f"   4. Toggle 'Public bucket' ON")
                        print(f"   5. Re-run this script")
                        return None
                else:
                    # Bucket exists but we got another error (likely permission)
                    # Assume bucket is there and continue
                    print(f"   ⚠️ Cannot verify bucket (RLS restrictions)")
                    print(f"   ℹ️ Assuming bucket '{bucket_name}' exists, continuing...")
                    return bucket_name
            
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            print(f"   ℹ️ Will attempt to continue anyway...")
            return bucket_name  # Try to continue despite error
    
    def upload_to_supabase(self, file_path, bucket_name, remote_path):
        """
        Upload file to Supabase storage
        """
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Upload to Supabase storage
            response = self.supabase_client.storage.from_(bucket_name).upload(
                remote_path,
                file_content,
                file_options={"content-type": "application/octet-stream"}
            )
            
            file_size = len(file_content) / 1024  # KB
            print(f"      ✅ Uploaded: {remote_path} ({file_size:.2f} KB)")
            
            return True
            
        except Exception as e:
            # If file exists, try to update it
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                try:
                    print(f"      📝 File exists, updating...")
                    # Remove old file
                    self.supabase_client.storage.from_(bucket_name).remove([remote_path])
                    # Upload new file
                    return self.upload_to_supabase(file_path, bucket_name, remote_path)
                except Exception as update_error:
                    print(f"      ❌ Error updating file: {update_error}")
                    return False
            else:
                print(f"      ❌ Upload error: {e}")
                return False
    
    def deploy_table(self, table_name, bucket_name='analytics-dwh'):
        """
        Export table from MySQL and deploy to Supabase
        """
        print(f"\n{'='*60}")
        print(f"🚀 DEPLOYING TABLE: {table_name}")
        print(f"{'='*60}")
        
        # Export table
        export_result = self.export_table_to_parquet(table_name)
        
        if export_result is None:
            print(f"   ⚠️ Skipping deployment for {table_name}")
            return False
        
        # Upload Parquet file
        print(f"\n📤 Uploading to Supabase:")
        parquet_remote = f"dwh/parquet/{table_name}.parquet"
        parquet_success = self.upload_to_supabase(
            export_result['parquet_path'],
            bucket_name,
            parquet_remote
        )
        
        # Upload CSV file
        csv_remote = f"dwh/csv/{table_name}.csv"
        csv_success = self.upload_to_supabase(
            export_result['csv_path'],
            bucket_name,
            csv_remote
        )
        
        # Upload metadata
        metadata_remote = f"dwh/metadata/{table_name}_metadata.json"
        metadata_success = self.upload_to_supabase(
            export_result['metadata_path'],
            bucket_name,
            metadata_remote
        )
        
        if parquet_success and csv_success and metadata_success:
            print(f"   ✅ {table_name} deployed successfully!")
            self.deployment_log.append({
                'table': table_name,
                'status': 'deployed',
                'parquet_url': f"{bucket_name}/{parquet_remote}",
                'csv_url': f"{bucket_name}/{csv_remote}",
                'metadata_url': f"{bucket_name}/{metadata_remote}"
            })
            return True
        else:
            print(f"   ⚠️ {table_name} partially deployed")
            return False
    
    def create_deployment_manifest(self):
        """
        Create a manifest file with deployment information
        """
        try:
            manifest = {
                'deployment_date': datetime.now().isoformat(),
                'source_database': self.mysql_config['database'],
                'supabase_url': self.supabase_url,
                'bucket': 'analytics-dwh',
                'tables_deployed': len([log for log in self.deployment_log if log.get('status') == 'deployed']),
                'total_tables': len(self.deployment_log),
                'deployment_log': self.deployment_log,
                'data_warehouse_schema': {
                    'dimensions': ['dim_listing', 'dim_host', 'dim_location', 'dim_room', 'dim_date'],
                    'facts': ['fact_listing']
                },
                'access_instructions': {
                    'parquet_files': 'dwh/parquet/{table_name}.parquet',
                    'csv_files': 'dwh/csv/{table_name}.csv',
                    'metadata': 'dwh/metadata/{table_name}_metadata.json'
                }
            }
            
            manifest_path = f"{self.export_dir}/deployment_manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=4, default=str)
            
            print(f"\n📋 Deployment manifest created: {manifest_path}")
            
            # Upload manifest to Supabase
            self.upload_to_supabase(
                manifest_path,
                'analytics-dwh',
                'dwh/deployment_manifest.json'
            )
            
            return manifest
            
        except Exception as e:
            print(f"❌ Error creating manifest: {e}")
            return None
    
    def deploy_all(self):
        """
        Deploy entire data warehouse to Supabase
        """
        print("\n" + "="*60)
        print("🚀 DATA WAREHOUSE DEPLOYMENT TO SUPABASE")
        print("="*60)
        print(f"Source: MySQL ({self.mysql_config['database']})")
        print(f"Target: Supabase Storage (analytics-dwh bucket)")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Connect to MySQL
        if not self.connect_mysql():
            return False
        
        # Connect to Supabase
        if not self.connect_supabase():
            return False
        
        # Create export directory
        if not self.create_export_directory():
            return False
        
        # Create/get bucket
        bucket_name = self.create_or_get_bucket('analytics-dwh')
        if not bucket_name:
            return False
        
        # Get all tables
        tables = self.get_all_tables()
        if not tables:
            return False
        
        # Deploy each table
        successful_deployments = 0
        for table in tables:
            if self.deploy_table(table, bucket_name):
                successful_deployments += 1
        
        # Create deployment manifest
        manifest = self.create_deployment_manifest()
        
        # Close MySQL connection
        self.close_mysql()
        
        # Print summary
        print("\n" + "="*60)
        print("📊 DEPLOYMENT SUMMARY")
        print("="*60)
        print(f"✅ Successfully deployed: {successful_deployments}/{len(tables)} tables")
        print(f"📦 Bucket: analytics-dwh")
        print(f"📁 Export directory: {self.export_dir}")
        
        if manifest:
            print(f"\n📋 Tables Deployed:")
            for log in self.deployment_log:
                if log.get('status') == 'deployed':
                    print(f"   ✅ {log['table']}")
        
        print("\n🔗 Access your data:")
        print(f"   Supabase Dashboard: {self.supabase_url}")
        print(f"   Storage > analytics-dwh > dwh/")
        
        print("\n💡 Usage:")
        print("   • Parquet files: Optimized for analytics (Pandas, DuckDB, etc.)")
        print("   • CSV files: Compatible with any tool")
        print("   • Metadata: Schema and statistics for each table")
        
        print("\n✅ DEPLOYMENT COMPLETE!")
        print("="*60)
        
        return successful_deployments == len(tables)


# ========================================
# CONFIGURATION
# ========================================

def load_config():
    """
    Load configuration from environment variables or return defaults
    """
    # MySQL Configuration
    mysql_config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', 'admin'),
        'database': os.getenv('MYSQL_DATABASE', 'airbnb_dwh'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'charset': 'utf8mb4'
    }
    
    # Supabase Configuration
    # Get these from: https://app.supabase.com/project/_/settings/api
    
    # Default to anon key, but allow service_role for full access
    supabase_url = os.getenv(
        'SUPABASE_URL', 'https://pthpniidapeauubawfsr.supabase.co')
    
    # Try service_role first (for RLS bypass), fallback to anon
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY') or 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB0aHBuaWlkYXBlYXV1YmF3ZnNyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI5MzA4NzQsImV4cCI6MjA3ODUwNjg3NH0.XzzlRXN5ZlWa71uGmMLWACVkcF1heuDP5EQ5z4-D7ao'
    
    return mysql_config, supabase_url, supabase_key


# ========================================
# MAIN EXECUTION
# ========================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   📊 DATA WAREHOUSE DEPLOYMENT TO SUPABASE                  ║
║                                                              ║
║   This script will:                                          ║
║   1. Export all tables from MySQL (airbnb_dwh)              ║
║   2. Convert to Parquet format (compressed, columnar)       ║
║   3. Upload to Supabase Storage (analytics-dwh bucket)      ║
║   4. Create metadata and deployment manifest                ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Load configuration
    mysql_config, supabase_url, supabase_key = load_config()
    
    # Check if Supabase credentials are set
    if supabase_url == 'YOUR_SUPABASE_URL' or supabase_key == 'YOUR_SUPABASE_ANON_KEY':
        print("❌ ERROR: Supabase credentials not set!")
        print("\n📝 Please set your Supabase credentials:")
        print("\nOption 1: Set environment variables:")
        print("   export SUPABASE_URL='your_supabase_url'")
        print("   export SUPABASE_KEY='your_supabase_anon_key'")
        print("\nOption 2: Edit this script and replace:")
        print("   - YOUR_SUPABASE_URL with your project URL")
        print("   - YOUR_SUPABASE_ANON_KEY with your anon/public key")
        print("\n🔗 Get credentials from:")
        print("   https://app.supabase.com/project/_/settings/api")
        print("\n" + "="*60)
        exit(1)
    
    # Initialize deployer
    deployer = DataWarehouseDeployer(mysql_config, supabase_url, supabase_key)
    
    # Deploy all tables
    success = deployer.deploy_all()
    
    # If deployment failed due to RLS, provide solution
    if not success:
        print("\n" + "="*60)
        print("⚠️ DEPLOYMENT FAILED - RLS POLICY ISSUE")
        print("="*60)
        print("\n🔒 Row-Level Security (RLS) is blocking file uploads.")
        print("\n💡 SOLUTION - Choose ONE:")
        print("\n📌 Option 1: Use Service Role Key (Recommended)")
        print("   1. Go to: https://app.supabase.com/project/_/settings/api")
        print("   2. Copy 'service_role' key (bottom of page)")
        print("   3. Run in PowerShell:")
        print('      $env:SUPABASE_SERVICE_KEY="your-service-role-key"')
        print("   4. Re-run: python deploy_to_supabase.py")
        print("\n📌 Option 2: Disable RLS on Storage Bucket")
        print("   1. Go to: https://app.supabase.com/project/_/storage/buckets")
        print("   2. Click 'analytics-dwh' bucket")
        print("   3. Settings → Policies")
        print("   4. Add policy: Allow INSERT/UPDATE for authenticated users")
        print("   OR disable RLS entirely (less secure)")
        print("\n⚠️ Note: Service role key has full access - use securely!")
        print("="*60)
    
    # Exit with appropriate code
    exit(0 if success else 1)
