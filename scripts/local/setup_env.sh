#!/bin/bash

# SkyEye Development Environment Setup Script
# This script helps you set up the LOCAL DEVELOPMENT environment quickly
# For production deployment, see DEPLOYMENT.md

set -e

echo "🐳 SkyEye Development Environment Setup"
echo "======================================="
echo "📍 Environment: Local Development (Docker Compose)"
echo "📖 For production deployment, see DEPLOYMENT.md"
echo ""

# Check if we're in the project directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: This script must be run from the project root directory"
    exit 1
fi

echo "📋 Setting up development environment..."

# Step 1: Check if .env file exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Copied .env.example to .env"
    else
        echo "❌ .env.example not found"
        exit 1
    fi
else
    echo "✅ .env file already exists"
fi

# Step 2: Generate SECRET_KEY if not set
if ! grep -q "^SECRET_KEY=" .env || grep -q "^SECRET_KEY=your-secret-key-here" .env; then
    echo "🔑 Generating SECRET_KEY..."
    ./scripts/generate_secret_key.sh --update-env
else
    echo "✅ SECRET_KEY already configured"
fi

# Step 3: Prompt for essential configuration
echo ""
echo "🔧 Please configure the following essential settings in your .env file:"
echo ""

# Check for empty or placeholder values
check_config() {
    local key=$1
    local description=$2
    local current_value=$(grep "^$key=" .env | cut -d'=' -f2- | tr -d '"')
    
    if [ -z "$current_value" ] || [ "$current_value" = "your-database-password" ] || [ "$current_value" = "your-cmc-api-key-here" ]; then
        echo "⚠️  $key: $description"
        return 1
    else
        echo "✅ $key: configured"
        return 0
    fi
}

needs_config=0

if ! check_config "POSTGRES_PASSWORD" "Database password"; then
    needs_config=1
fi

if ! check_config "COINMARKETCAP_API_KEY" "CoinMarketCap API key"; then
    needs_config=1
fi

echo ""

if [ $needs_config -eq 1 ]; then
    echo "📝 Please edit the .env file and configure the missing values:"
    echo "   nano .env"
    echo ""
    echo "💡 After configuration, run the environment check:"
    echo "   python scripts/check_env.py"
else
    echo "🎉 All essential configuration looks good!"
    echo ""
    echo "🔍 Running environment check..."
    if python scripts/check_env.py; then
        echo ""
        echo "✅ Environment setup complete! You can now start development:"
        echo ""
        echo "🐘 Start database services (Docker Compose):"
        echo "   ./scripts/manage_docker.sh up"
        echo ""
        echo "🔄 Run database migrations:"
        echo "   uv run python manage.py migrate"
        echo ""
        echo "🚀 Start development server:"
        echo "   uv run python manage.py runserver"
        echo ""
        echo "📝 Optional: Start background tasks:"
        echo "   ./scripts/manage_celery.sh start"
    fi
fi

echo ""
echo "📚 For more information, see ENV_SETUP.md"