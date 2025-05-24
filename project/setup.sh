#!/bin/bash

echo "🔧 Creating virtual environment (.venv)..."
python3 -m venv .venv

echo "✅ Activating virtual environment..."
source .venv/bin/activate

echo "⬆️ Upgrading pip..."
pip install --upgrade pip

if [ -f requirements.txt ]; then
  echo "📦 Installing dependencies from requirements.txt..."
  pip install -r requirements.txt
else
  echo "⚠️ requirements.txt not found. Skipping dependency install."
fi

echo "✅ Setup complete. Your virtual environment is ready!"
echo "👉 To activate later, run: source .venv/bin/activate"
