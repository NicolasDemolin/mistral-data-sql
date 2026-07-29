"""
Database Initializer for ACPR Solvency II / SURFI Financial & Regulatory Database.
Sets up local SQLite database populated with realistic regulatory data for AXA and peers.
"""

import sqlite3
from pathlib import Path
from config import DB_PATH

def init_db(db_path: Path = DB_PATH):
    """Creates tables and seeds ACPR regulatory data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Table Entities (Assureurs / Groupe)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lei_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        short_code TEXT NOT NULL,
        country TEXT NOT NULL,
        sector TEXT NOT NULL
    );
    """)

    # 2. Table Solvency II QRT S.23.01 - Own Funds (Fonds Propres)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS s2301_own_funds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id INTEGER NOT NULL,
        period TEXT NOT NULL, -- e.g. 2023-Q4
        tier1_unrestricted REAL NOT NULL, -- Fonds propres Tier 1 non restreints
        tier1_restricted REAL NOT NULL,   -- Fonds propres Tier 1 restreints
        tier2 REAL NOT NULL,              -- Fonds propres Tier 2
        tier3 REAL NOT NULL,              -- Fonds propres Tier 3
        total_eligible_own_funds_scr REAL NOT NULL, -- Fonds propres éligibles pour couvrir le SCR
        total_eligible_own_funds_mcr REAL NOT NULL, -- Fonds propres éligibles pour couvrir le MCR
        scr_amount REAL NOT NULL,         -- Capital Requis de Solvabilité (SCR)
        mcr_amount REAL NOT NULL,         -- Capital Requis Minimum (MCR)
        solvency_ratio_pct REAL NOT NULL, -- Ratio de solvabilité Solvabilité II (%)
        currency TEXT DEFAULT 'EUR',
        FOREIGN KEY (entity_id) REFERENCES entities (id)
    );
    """)

    # 3. Table Solvency II QRT S.02.01 - Balance Sheet (Bilan Prudentiel)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS s0201_balance_sheet (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id INTEGER NOT NULL,
        period TEXT NOT NULL,
        total_assets REAL NOT NULL,                 -- Total Actif
        investments_financial REAL NOT NULL,        -- Placements financiers
        cash_and_equivalents REAL NOT NULL,         -- Trésorerie
        technical_provisions REAL NOT NULL,         -- Provisions techniques
        total_liabilities REAL NOT NULL,            -- Total Passif
        excess_assets_over_liabilities REAL NOT NULL,-- Excédent de l'actif sur le passif
        currency TEXT DEFAULT 'EUR',
        FOREIGN KEY (entity_id) REFERENCES entities (id)
    );
    """)

    # 4. Table Metadata Catalog / Regulatory Cell Coordinates Dictionary
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_dictionary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        column_name TEXT NOT NULL,
        qrt_table_code TEXT NOT NULL,
        qrt_row_code TEXT NOT NULL,
        qrt_col_code TEXT NOT NULL,
        concept_fr TEXT NOT NULL,
        concept_en TEXT NOT NULL,
        unit TEXT NOT NULL,
        description TEXT NOT NULL
    );
    """)

    # --- SEED DATA ---
    cursor.execute("DELETE FROM entities;")
    cursor.execute("DELETE FROM s2301_own_funds;")
    cursor.execute("DELETE FROM s0201_balance_sheet;")
    cursor.execute("DELETE FROM data_dictionary;")

    # Insert Entities
    entities_data = [
        ("969500A242M0A8951963", "AXA SA", "AXA", "FR", "Insurance Group"),
        ("969500A453G92150963", "AXA FRANCE VIE", "AXA_VIE", "FR", "Life Insurance"),
        ("529900560FKA8EATDM85", "ALLIANZ SE", "ALLIANZ", "DE", "Insurance Group"),
        ("549300T5WLHXQV231454", "GENERALI ASSICURAZIONI", "GENERALI", "IT", "Insurance Group"),
    ]
    cursor.executemany("""
    INSERT INTO entities (lei_code, name, short_code, country, sector)
    VALUES (?, ?, ?, ?, ?);
    """, entities_data)

    # Insert S2301 Own Funds (Fonds propres AXA = 52.45 Mds € pour SCR)
    s2301_data = [
        # entity_id, period, tier1_unrest, tier1_rest, tier2, tier3, total_scr, total_mcr, scr, mcr, ratio
        (1, "2023-Q4", 44800000000.0, 2150000000.0, 5200000000.0, 300000000.0, 52450000000.0, 46950000000.0, 23100000000.0, 10400000000.0, 227.06, "EUR"),
        (1, "2022-Q4", 42100000000.0, 2000000000.0, 4900000000.0, 250000000.0, 49250000000.0, 44100000000.0, 22900000000.0, 10200000000.0, 215.07, "EUR"),
        (2, "2023-Q4", 18500000000.0, 900000000.0, 2100000000.0, 100000000.0, 21600000000.0, 19400000000.0, 9800000000.0, 4400000000.0, 220.41, "EUR"),
        (3, "2023-Q4", 51200000000.0, 2800000000.0, 6100000000.0, 400000000.0, 60500000000.0, 54000000000.0, 26400000000.0, 11800000000.0, 229.16, "EUR"),
    ]
    cursor.executemany("""
    INSERT INTO s2301_own_funds 
    (entity_id, period, tier1_unrestricted, tier1_restricted, tier2, tier3, total_eligible_own_funds_scr, total_eligible_own_funds_mcr, scr_amount, mcr_amount, solvency_ratio_pct, currency)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, s2301_data)

    # Insert S0201 Balance Sheet (Bilan Prudentiel AXA Actif = 680 Mds €)
    s0201_data = [
        (1, "2023-Q4", 680500000000.0, 510000000000.0, 25000000000.0, 575000000000.0, 628050000000.0, 52450000000.0, "EUR"),
        (3, "2023-Q4", 720000000000.0, 540000000000.0, 31000000000.0, 610000000000.0, 659500000000.0, 60500000000.0, "EUR"),
    ]
    cursor.executemany("""
    INSERT INTO s0201_balance_sheet
    (entity_id, period, total_assets, investments_financial, cash_and_equivalents, technical_provisions, total_liabilities, excess_assets_over_liabilities, currency)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, s0201_data)

    # Insert Metadata Catalog / Data Dictionary with exact ACPR / EIOPA QRT cell coordinates
    dictionary_data = [
        ("s2301_own_funds", "total_eligible_own_funds_scr", "S.23.01.01", "R0010", "C0010", "Montant des fonds propres éligibles pour couvrir le SCR", "Total eligible own funds to meet the SCR", "EUR", "Fonds propres prudentiels totaux selon Solvabilité II"),
        ("s2301_own_funds", "tier1_unrestricted", "S.23.01.01", "R0040", "C0010", "Fonds propres Tier 1 non restreints", "Tier 1 unrestricted own funds", "EUR", "Capital de haute qualité sans contrainte d absorption des pertes"),
        ("s2301_own_funds", "tier1_restricted", "S.23.01.01", "R0050", "C0010", "Fonds propres Tier 1 restreints", "Tier 1 restricted own funds", "EUR", "Instruments subordonnés Tier 1 restreints"),
        ("s2301_own_funds", "tier2", "S.23.01.01", "R0070", "C0010", "Fonds propres Tier 2", "Tier 2 own funds", "EUR", "Titres subordonnés et dettes subordonnées Tier 2"),
        ("s2301_own_funds", "tier3", "S.23.01.01", "R0090", "C0010", "Fonds propres Tier 3", "Tier 3 own funds", "EUR", "Créances fiscales différées nettes éligibles"),
        ("s2301_own_funds", "scr_amount", "S.23.01.01", "R0580", "C0010", "Capital Requis de Solvabilité (SCR)", "Solvency Capital Requirement", "EUR", "Exigence de capital globale Solvabilité II"),
        ("s2301_own_funds", "solvency_ratio_pct", "S.23.01.01", "R0620", "C0010", "Ratio de Solvabilité II", "Solvency II ratio", "%", "Ratio Fonds Propres Eligibles / SCR"),
        ("s0201_balance_sheet", "total_assets", "S.02.01.01", "R0500", "C0010", "Total de l'actif", "Total assets", "EUR", "Total Bilan Prudentiel Actif"),
        ("s0201_balance_sheet", "excess_assets_over_liabilities", "S.02.01.01", "R0300", "C0010", "Excédent de l'actif sur le passif", "Excess of assets over liabilities", "EUR", "Valeur nette d entreprise selon Solvabilité II"),
    ]
    cursor.executemany("""
    INSERT INTO data_dictionary
    (table_name, column_name, qrt_table_code, qrt_row_code, qrt_col_code, concept_fr, concept_en, unit, description)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, dictionary_data)

    conn.commit()
    conn.close()
    print(f"Database initialized successfully at: {db_path}")

if __name__ == "__main__":
    init_db()
