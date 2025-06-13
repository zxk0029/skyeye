#!/usr/bin/env python3
"""
Check environment variables configuration for SkyEye project.
Usage: python scripts/check_env.py
"""

import os
import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def load_env_file():
    """Load environment variables from .env file"""
    env_file = project_root / '.env'
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    os.environ[key] = value

def check_env_vars(quiet=False):
    """Check if all required environment variables are set."""
    
    # Required environment variables
    required_vars = [
        'SECRET_KEY',
        'POSTGRES_PASSWORD',
        'COINMARKETCAP_API_KEY',
    ]
    
    # Optional but recommended variables
    recommended_vars = [
        'DEBUG',
        'ALLOWED_HOSTS',
        'POSTGRES_DB',
        'POSTGRES_USER',
        'REDIS_URL',
        'CELERY_BROKER_URL',
    ]
    
    if not quiet:
        print("🔍 Checking environment variables...")
        print("=" * 50)
    
    # Check required variables
    missing_required = []
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing_required.append(var)
            if not quiet:
                print(f"❌ {var}: NOT SET (REQUIRED)")
        else:
            if not quiet:
                # Mask sensitive values
                if 'KEY' in var or 'PASSWORD' in var:
                    display_value = value[:8] + "..." if len(value) > 8 else "***"
                else:
                    display_value = value
                print(f"✅ {var}: {display_value}")
    
    if not quiet:
        print("\n" + "=" * 50)
    
    # Check recommended variables
    missing_recommended = []
    for var in recommended_vars:
        value = os.environ.get(var)
        if not value:
            missing_recommended.append(var)
            if not quiet:
                print(f"⚠️  {var}: NOT SET (recommended)")
        else:
            if not quiet:
                print(f"✅ {var}: {value}")
    
    if not quiet:
        print("\n" + "=" * 50)
    
    # Summary
    if missing_required:
        if not quiet:
            print(f"❌ MISSING REQUIRED VARIABLES: {', '.join(missing_required)}")
            print("   Please set these in your .env file before running the application.")
        return False
    
    if missing_recommended and not quiet:
        print(f"⚠️  MISSING RECOMMENDED VARIABLES: {', '.join(missing_recommended)}")
        print("   Consider setting these for better configuration.")
    
    if not quiet:
        print("✅ All required environment variables are set!")
        
        # Check .env file existence
        env_file = project_root / '.env'
        if env_file.exists():
            print(f"✅ .env file found at {env_file}")
        else:
            print(f"⚠️  .env file not found. Copy .env.example to .env and fill in your values.")
    
    return True

def check_django_settings():
    """Try to import Django settings to check for configuration errors."""
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skyeye.settings')
        import django
        from django.conf import settings
        
        # This will trigger settings loading and validation
        django.setup()
        
        print("✅ Django settings loaded successfully!")
        print(f"✅ DEBUG mode: {settings.DEBUG}")
        print(f"✅ Database: {settings.DATABASES['default']['NAME']}")
        print(f"✅ Cache backend: {settings.CACHES['default']['BACKEND']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Django settings error: {e}")
        return False

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Check SkyEye environment configuration')
    parser.add_argument('--quiet', action='store_true', help='Suppress detailed output')
    args = parser.parse_args()
    
    if not args.quiet:
        print("SkyEye Environment Configuration Checker")
        print("=" * 50)
    
    # Load .env file first
    load_env_file()
    
    if not args.quiet:
        # Check if we're in a virtual environment
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            print("✅ Virtual environment detected")
        else:
            print("⚠️  No virtual environment detected. Consider using 'uv venv' or 'python -m venv'")
        
        print()
    
    # Check environment variables
    env_ok = check_env_vars(quiet=args.quiet)
    
    if not args.quiet:
        print()
    
    # Check Django settings if env vars are OK
    if env_ok:
        if not args.quiet:
            django_ok = check_django_settings()
            
            if django_ok:
                print("\n🎉 Configuration check passed! You're ready to run the application.")
            else:
                print("\n❌ Configuration check failed. Please fix the Django settings errors.")
                sys.exit(1)
        # In quiet mode, just exit with 0 if env vars are OK
    else:
        if not args.quiet:
            print("\n❌ Configuration check failed. Please set the required environment variables.")
        sys.exit(1)