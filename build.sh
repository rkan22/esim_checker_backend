#!/usr/bin/env bash
# exit on error
set -o errexit

echo "🔧 Starting build process..."

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies (no cache to avoid stale packages)
echo "📦 Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --no-input

# Run migrations
echo "🗄️  Running database migrations..."
python manage.py migrate

echo "✅ Build complete!"

