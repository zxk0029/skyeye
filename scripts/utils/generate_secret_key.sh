#!/bin/bash

# Generate a secure Django SECRET_KEY using Django's official method
# Usage: ./scripts/generate_secret_key.sh [--update-env]

set -e  # Exit on any error

echo "🔑 Generating Django SECRET_KEY..."
echo "=================================================="

# Check if we're in the project directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: This script must be run from the project root directory"
    echo "   Please run: cd /path/to/skyeye && ./scripts/generate_secret_key.sh"
    exit 1
fi

# Generate the secret key using Django's official method
echo "🔄 Generating key using Django's official method..."
SECRET_KEY=$(uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

if [ $? -ne 0 ] || [ -z "$SECRET_KEY" ]; then
    echo "❌ Failed to generate SECRET_KEY"
    echo "   Make sure Django is installed and accessible via 'uv run python'"
    exit 1
fi

echo "✅ Generated SECRET_KEY:"
echo "$SECRET_KEY"
echo ""

# Check if --update-env flag is provided
if [ "$1" = "--update-env" ] || [ "$1" = "-u" ]; then
    if [ ! -f ".env" ]; then
        echo "📝 Creating .env file..."
        touch .env
    fi
    
    # Check if SECRET_KEY already exists in .env
    if grep -q "^SECRET_KEY=" .env; then
        # Get current SECRET_KEY value
        current_key=$(grep "^SECRET_KEY=" .env | cut -d'=' -f2)
        
        # Only backup if there's a meaningful existing key (not empty or placeholder)
        if [ -n "$current_key" ] && [ "$current_key" != "your-secret-key-here" ]; then
            echo "⚠️  SECRET_KEY already exists in .env file."
            echo "   Current value will be backed up to .env.backup"
            cp .env .env.backup
        fi
        
        # Replace existing SECRET_KEY while preserving file structure
        # Use a more portable approach with awk
        awk -v new_key="SECRET_KEY=$SECRET_KEY" '
        /^SECRET_KEY=/ { print new_key; next }
        { print }
        ' .env > .env.tmp && mv .env.tmp .env
        echo "✅ Updated SECRET_KEY in .env file"
    else
        # Add new SECRET_KEY
        echo "SECRET_KEY=$SECRET_KEY" >> .env
        echo "✅ Added SECRET_KEY to .env file"
    fi
    echo ""
else
    echo "📝 To add this to your .env file:"
    echo "SECRET_KEY=$SECRET_KEY"
    echo ""
    echo "💡 Quick commands:"
    echo "   Manual: echo 'SECRET_KEY=$SECRET_KEY' >> .env"
    echo "   Auto:   ./scripts/generate_secret_key.sh --update-env"
    echo ""
fi

echo "⚠️  Security reminders:"
echo "   • Keep this key secret and never commit it to version control"
echo "   • Use different keys for development and production environments"
echo "   • Rotate keys periodically for better security"