"""Start the app:  python run.py   (opens on http://127.0.0.1:5000)"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
