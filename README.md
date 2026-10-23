# Offline ERP POS Starter

A practical offline-first commercial ERP/POS starter built in Python for Windows desktop use.

Features included:
- Item master
- POS billing screen
- Invoice creation
- Stock ledger
- Customer and supplier tables
- License key generation and verification
- SQLite database with schema
- Modular service-layer design

## Stack
- Python 3.11+
- SQLite
- Tkinter (desktop UI)
- cryptography

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python app.py
```

## License generation

```bash
python keygen.py --customer "ABC Electronics" --edition professional --users 5 --days 365 --output license.json
```

## Notes

This is a starter foundation for a commercial ERP/POS product. It is designed to be extended into a Busy/MARG-like solution with branches, purchase module, accounts, GST, messaging, and licensing controls.
