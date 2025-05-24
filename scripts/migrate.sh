#!/bin/bash

# Create necessary directories if they don't exist
mkdir -p app/{db/{migrations},models,schemas,api,services,ingestion,valuation,analytics,commons} ui/components scripts docs notebooks tests/{unit,integration,e2e}

# Move files to their new locations
mv app.py ui/streamlit_app.py
mv Home.py ui/components/
mv menu.py ui/components/
mv database.py app/db/session.py
mv db.py app/db/base.py
mv price_service.py app/services/
mv analytics.py app/analytics/portfolio.py
mv reporting.py app/valuation/
mv ingestion.py app/ingestion/loader.py
mv check_*.py scripts/
mv test_*.py tests/unit/

# Create __init__.py files
touch app/__init__.py
touch app/db/__init__.py
touch app/models/__init__.py
touch app/schemas/__init__.py
touch app/api/__init__.py
touch app/services/__init__.py
touch app/ingestion/__init__.py
touch app/valuation/__init__.py
touch app/analytics/__init__.py
touch app/commons/__init__.py
touch ui/__init__.py
touch ui/components/__init__.py
touch scripts/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
touch tests/e2e/__init__.py

echo "Migration complete! Please review the changes and update import statements." 