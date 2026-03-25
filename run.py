#!/usr/bin/env python3
"""ICTMD Türkiye Akademik Takip — Başlatma scripti"""
from app import app

if __name__ == "__main__":
    print("=" * 50)
    print("  ICTMD Türkiye Akademik Yayın Takip Sistemi")
    print("=" * 50)
    print("  Adres: http://localhost:5000")
    print("  Durdurmak için: Ctrl+C")
    print("=" * 50)
    app.run(debug=False, host="0.0.0.0", port=5000)
