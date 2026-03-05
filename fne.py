import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
import pandas as pd
import pyodbc
from datetime import datetime
from tkinter import messagebox
from tkcalendar import DateEntry  # pip install tkcalendar
import os

# === Lecture du fichier de connexion ===
def lire_connexion():
    fichier = "connexion.txt"
    if not os.path.exists(fichier):
        messagebox.showerror("Fichier manquant", f"Le fichier '{fichier}' n'existe pas.\nCréez-le avec les paramètres de connexion.")
        return None
    params = {}
    try:
        with open(fichier, "r", encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne and "=" in ligne:
                    cle, valeur = ligne.split("=", 1)
                    params[cle.strip()] = valeur.strip()
        return params
    except Exception as e:
        messagebox.showerror("Erreur lecture", f"Impossible de lire le fichier de connexion :\n{e}")
        return None

# === Connexion à SQL Server ===
def connecter():
    params = lire_connexion()
    if not params:
        return None
    conn_str = (
        r'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER={params.get("serveur")};'
        f'DATABASE={params.get("base")};'
        f'UID={params.get("utilisateur")};'
        f'PWD={params.get("motdepasse")};'
    )
    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        return conn
    except Exception as e:
        messagebox.showerror("Erreur de connexion", f"Connexion échouée :\n{e}")
        return None

# === Récupération des factures ===
def charger_factures():
    conn = connecter()
    if not conn:
        return

    # Récupération des dates au format YYYYMMDD (safe pour SQL Server français)
    date_du_str = date_debut.get_date().strftime('%Y%m%d')
    date_au_str = date_fin.get_date().strftime('%Y%m%d')
    
    # La date de fin +1 jour pour inclure toute la journée "au"
    from datetime import timedelta
    date_au_plus_un = (date_fin.get_date() + timedelta(days=1)).strftime('%Y%m%d')

    origine = entry_origine.get().strip()
    type_doc = var_type.get()  # 0=Tous, 1=Facture, 2=Avoir

    conditions = [
        "e.DO_Domaine = 0",
        "e.DO_Statut = 2",  # Validée
        f"e.DO_Date >= '{date_du_str}'",
        f"e.DO_Date < '{date_au_plus_un}'"  # < date_suivante pour inclure le jour "au"
    ]

    if type_doc == 1:
        conditions.append("e.DO_Type = 6")  # Facture
    elif type_doc == 2:
        conditions.append("e.DO_Type = 5")  # Avoir

    if origine:
        conditions.append(f"e.DO_Piece LIKE '%{origine}%'")

    where_clause = " AND ".join(conditions)

    query = f"""
    SELECT 
        e.DO_Piece AS NumeroFacture,
        CONVERT(varchar, e.DO_Date, 103) AS Date,
        ISNULL(e.DO_Ref, '') AS Libelle,  -- On prend la référence comme libellé (souvent utilisé)
        e.DO_Tiers AS CodeClient,
        SUM(ISNULL(l.DL_MontantHT, 0)) AS TotalHT,
        SUM(ISNULL(l.DL_MontantTTC, 0)) AS TotalTTC
    FROM F_DOCENTETE e
    INNER JOIN F_DOCLIGNE l 
        ON e.DO_Piece = l.DO_Piece 
        AND e.DO_Type = l.DO_Type 
        AND e.DO_Domaine = l.DO_Domaine
    WHERE {where_clause}
    GROUP BY e.DO_Piece, e.DO_Date, e.DO_Tiers, e.DO_Ref
    ORDER BY e.DO_Date DESC, e.DO_Piece DESC
    """

    try:
        df = pd.read_sql(query, conn)
        afficher_dans_tableau(df)
    except Exception as e:
        messagebox.showerror("Erreur requête", f"Erreur SQL :\n{e}\n\nRequête exécutée :\n{query[:500]}...")
    finally:
        conn.close()

# === Affichage dans le tableau ===
def afficher_dans_tableau(df):
    # Vider le tableau
    for item in tree.get_children():
        tree.delete(item)

    if df.empty:
        messagebox.showinfo("Résultat", "Aucune facture trouvée avec ces critères.")
        return

    for _, row in df.iterrows():
        tree.insert("", "end", values=(
            False,  # Checkbox (on gère manuellement)
            row["NumeroFacture"],
            row["Date"],
            row["Libelle"],
            row["CodeClient"],
            f"{row['TotalHT']:,.2f}".replace(",", " "),
            f"{row['TotalTTC']:,.2f}".replace(",", " ")
        ))

# === Main Window ===
root = ThemedTk(theme="arc")  # Thème moderne et propre (arc, equilux, breeze...)
root.title("KM TECH - Factures Sage avec CodeQR")
root.geometry("1100x700")
root.configure(bg="#2b2b2b")

# Barre de titre personnalisée
title_bar = ttk.Frame(root, relief="raised", style="Title.TFrame")
title_bar.pack(fill="x")
ttk.Label(title_bar, text="KM TECH", font=("Helvetica", 14, "bold"), foreground="white", background="#2b2b2b").pack(side="left", padx=10, pady=5)

# Filtres
filter_frame = ttk.Frame(root, padding=10)
filter_frame.pack(fill="x")

ttk.Label(filter_frame, text="Facture N°: FA256319").grid(row=0, column=0, sticky="w")
ttk.Label(filter_frame, text="Facture d'origine N°:", font=("Helvetica", 10, "bold")).grid(row=0, column=1, padx=(20,5))
entry_origine = ttk.Entry(filter_frame, width=20)
entry_origine.grid(row=0, column=2)

ttk.Label(filter_frame, text="Facture du", font=("Helvetica", 10)).grid(row=0, column=3, padx=(40,5))
date_debut = DateEntry(filter_frame, date_pattern='dd/mm/yyyy', width=12)
date_debut.grid(row=0, column=4)
date_debut.set_date("01/01/2025")

ttk.Label(filter_frame, text="au", font=("Helvetica", 10)).grid(row=0, column=5)
date_fin = DateEntry(filter_frame, date_pattern='dd/mm/yyyy', width=12)
date_fin.grid(row=0, column=6)
date_fin.set_date(datetime.today())

# Boutons radio
var_type = tk.IntVar(value=0)
ttk.Radiobutton(filter_frame, text="Tous", variable=var_type, value=0).grid(row=0, column=7, padx=20)
ttk.Radiobutton(filter_frame, text="Facture", variable=var_type, value=1).grid(row=0, column=8)
ttk.Radiobutton(filter_frame, text="Avoir", variable=var_type, value=2).grid(row=0, column=9)

# Bouton charger
btn_charger = ttk.Button(filter_frame, text="Charger", command=charger_factures)
btn_charger.grid(row=0, column=10, padx=20)

# Tableau
columns = ("check", "NumeroFacture", "Date", "Libelle", "CodeClient", "TotalHT", "TotalTTC")
tree = ttk.Treeview(root, columns=columns, show="headings", height=20)

tree.heading("check", text="")
tree.column("check", width=40, anchor="center")

tree.heading("NumeroFacture", text="NumeroFacture")
tree.column("NumeroFacture", width=150)

tree.heading("Date", text="Date")
tree.column("Date", width=100)

tree.heading("Libelle", text="Libelle")
tree.column("Libelle", width=200)

tree.heading("CodeClient", text="CodeClient")
tree.column("CodeClient", width=120)

tree.heading("TotalHT", text="TotalHT")
tree.column("TotalHT", width=120, anchor="e")

tree.heading("TotalTTC", text="TotalTTC")
tree.column("TotalTTC", width=120, anchor="e")

tree.pack(fill="both", expand=True, padx=10, pady=10)

# Scrollbar
vsb = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=vsb.set)
vsb.pack(side="right", fill="y")

# Bouton en bas
btn_certifier = ttk.Button(root, text="Certifier la facture", style="Accent.TButton")
btn_certifier.pack(pady=10)

# Style accent pour le bouton
style = ttk.Style()
style.configure("Accent.TButton", font=("Helvetica", 10, "bold"))

root.mainloop()