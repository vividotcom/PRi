from flask import Flask, render_template, request, jsonify, send_file
import os
import sqlite3
import json
from datetime import datetime, date
import uuid
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

app = Flask(__name__)

# ─── DATABASE ─────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pr_data.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pr (
            id          TEXT PRIMARY KEY,
            number      TEXT NOT NULL,
            title       TEXT NOT NULL,
            category    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'en-cours',
            created_date TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS task (
            pr_id       TEXT NOT NULL,
            task_id     TEXT NOT NULL,
            title       TEXT,
            description TEXT,
            done        INTEGER NOT NULL DEFAULT 0,
            date_prev   TEXT DEFAULT '',
            date_reelle TEXT DEFAULT '',
            note        TEXT DEFAULT '',
            PRIMARY KEY (pr_id, task_id),
            FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
        )
    """)
    # Migration: add date_prev / date_reelle columns if they don't exist yet
    existing = [row[1] for row in c.execute("PRAGMA table_info(task)").fetchall()]
    if "date_prev" not in existing:
        c.execute("ALTER TABLE task ADD COLUMN date_prev TEXT DEFAULT ''")
    if "date_reelle" not in existing:
        c.execute("ALTER TABLE task ADD COLUMN date_reelle TEXT DEFAULT ''")
    
    # Migration: add custom_steps column to PR table if it doesn't exist
    pr_cols = [row[1] for row in c.execute("PRAGMA table_info(pr)").fetchall()]
    if "custom_steps" not in pr_cols:
        c.execute("ALTER TABLE pr ADD COLUMN custom_steps TEXT DEFAULT ''")
    
    # Migration: add base_category column to PR table if it doesn't exist
    pr_cols = [row[1] for row in c.execute("PRAGMA table_info(pr)").fetchall()]
    if "base_category" not in pr_cols:
        c.execute("ALTER TABLE pr ADD COLUMN base_category TEXT DEFAULT ''")
        # Backfill: set base_category = category for all existing rows
        c.execute("UPDATE pr SET base_category = category WHERE base_category = '' OR base_category IS NULL")
    
    # Migration: add lost_days column to PR table if it doesn't exist
    pr_cols = [row[1] for row in c.execute("PRAGMA table_info(pr)").fetchall()]
    if "lost_days" not in pr_cols:
        c.execute("ALTER TABLE pr ADD COLUMN lost_days INTEGER DEFAULT 0")
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS document (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'En attente',
            color       TEXT NOT NULL DEFAULT '#3498db',
            done        INTEGER NOT NULL DEFAULT 0,
            created_date TEXT NOT NULL
        )
    """)
    
    # PR-specific documents table (legacy, kept for compatibility)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pr_document (
            id          TEXT PRIMARY KEY,
            pr_id       TEXT NOT NULL,
            doc_id      TEXT NOT NULL,
            name        TEXT NOT NULL,
            done        INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
        )
    """)

    # Per-PR document checklist table
    c.execute("""
        CREATE TABLE IF NOT EXISTS pr_doc_checklist (
            id          TEXT PRIMARY KEY,
            pr_id       TEXT NOT NULL,
            name        TEXT NOT NULL,
            done        INTEGER NOT NULL DEFAULT 0,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

# ─── DEFAULT DOCUMENT CHECKLISTS ─────────────────────────────────────────────
DEFAULT_DOCS = {
    "ED": [
        "PR (ARIBA)",
        "Fiche Justification Entente Directe",
        "PV CM de Concertation",
        "PV Réunion 1er binôme",
        "Rapport technique validé du SU",
        "PV d'Ouverture Technique",
        "Offre initial (OI)",
        "PV d'Ouverture Commerciale (OI)",
        "Offres améliorées ( 1, 2, 3 ..)",
        "Rapport de binôme",
        "PV de Commission de Marchés (Adjudication)",
        "Copie du mail OK vert de la CM du chef de division",
        "Fiche Décision d'Entente Directe",
        "Copie Contrat (si Montant > 1M)",
        "Lettre de Notification (Si contrat)",
        "BC (ARIBA)",
        "Copie imprimée de tous les courriels relatifs au dossier",
    ],
    "CR": [
        "PR (ARIBA)",
        "PV Réunion 1er binôme",
        "Rapport technique validé du SU",
        "PV d'Ouverture Technique",
        "Offres initiales (OI)",
        "PV d'Ouverture des OI",
        "Rapport d'Evaluation des OI",
        "Offres Améliorées 1 (OA1)",
        "PV d'Ouverture des OA1",
        "Rapport d'Evaluation des OA1",
        "Offres Améliorées 2 (OA2)",
        "PV d'Ouverture des OA2",
        "Rapport d'Evaluation des OA2",
        "Rapport de binôme",
        "PV de Commission de Marchés",
        "Copie du mail OK vert de la CM du chef de division",
        "Copie Contrat (si Montant > 1M)",
        "Lettre de Notification (Si contrat)",
        "BC (ARIBA)",
        "Copie imprimée de tous les courriels relatifs au dossier",
    ],
    "REG": [
        "PR (ARIBA)",
        "Fiche Justification Entente Directe",
        "PV CM de Concertation",
        "PV Réunion 1er binôme",
        "Devis (Offre initial)",
        "Offres améliorées",
        "Rapport de binôme",
        "PV de Commission de Marchés (Adjudication)",
        "Copie du mail contenant l'OK vert de ce dossier d'après la CM du chef de division",
        "Fiche Décision d'Entente Directe",
        "BC (ARIBA)",
        "Copie imprimée de tous les courriels (mail) relatifs aux événements liés à ce dossier",
    ],
}
# COU uses same docs as CR
DEFAULT_DOCS["COU"] = DEFAULT_DOCS["CR"]


def seed_pr_docs(conn, pr_id: str, base_category: str):
    """Insert default document checklist rows for a newly created PR."""
    docs = DEFAULT_DOCS.get(base_category, [])
    for i, name in enumerate(docs):
        doc_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO pr_doc_checklist (id, pr_id, name, done, sort_order) VALUES (?,?,?,0,?)",
            (doc_id, pr_id, name, i)
        )


# ─── PROCESSING TIME LIMITS (in weeks) ────────────────────────────────────────
PROCESSING_LIMITS = {
    "ED": {
        "max_weeks": 10,
        "steps": {
            "Délai de dépot des offres": 3,
            "Etude technique": 2,
            "Négociation": 2,
            "Contractualisation": 3,
        }
    },
    "CR": {
        "max_weeks": 11,
        "steps": {
            "Délai de dépot des offres": 4,
            "Etude technique": 2,
            "Négociation": 2,
            "Contractualisation": 3,
        }
    },
    "COU": {
        "max_weeks": 14,
        "steps": {
            "Délai de dépot des offres": 5,
            "Etude technique": 3,
            "Négociation": 3,
            "Contractualisation": 3,
        }
    },
    "REG": {
        "max_weeks": 10,
        "steps": {
            "Délai de dépot des offres": 3,
            "Etude technique:": 2,
            "Négociation": 2,
            "Contractualisation": 3,
        }
    },
}

# ─── STEPS DEFINITIONS ────────────────────────────────────��───────────────────
STEPS_DATA = {
    "ED": [
        {"id": 1,  "title": "Demande et vérification de la fiche de justification de l'ED",
         "desc": "Demander la fiche de justification de l'ED, dûment signée et cachetée par la direction du SU, et vérifier au préalable si elle est déjà disponible en pièces jointes sur Ariba."},
        {"id": 2,  "title": "Programmation du dossier en Commission de Marchés (CM)",
         "desc": "Programmer le dossier pour concertation en CM."},
        {"id": 3,  "title": "Suite à la concertation",
         "desc": "Après la concertation, obtenir l'OK pour faire aboutir le dossier ou poursuivre la procédure."},
        {"id": 4,  "title": "Rédaction et envoi du PV de la CM",
         "desc": "Rédiger le procès-verbal (PV) de la CM (pour concertation) et l'envoyer, pour signature, en réponse au mail de programmation de la CM, en plaçant le Chef de Division de la section CC en tête des destinataires."},
        {"id": 5,  "title": "Demande du BOQ et des spécifications techniques",
         "desc": "Envoyer au SU un mail, en réponse au mail de notification Ariba du PR, afin de demander le BOQ et les spécifications techniques."},
        {"id": 6,  "title": "Rédaction du PV de la première réunion de binôme",
         "desc": "Après réception de la réponse du SU, rédiger le procès-verbal de la première réunion de binôme."},
        {"id": 7,  "title": "Transmission du PV de la première réunion de binôme",
         "desc": "Envoyer le PV de la première réunion de binôme au SU, en mettant en copie la hiérarchie achats et la hiérarchie SU. (Hors directeurs)"},
        {"id": 8,  "title": "Réception des spécifications techniques",
         "desc": "Ajouter le BOQ comme tableau, enregistrer sous forme de PDF, joindre les conditions générales d'achat PDF et envoyer le mail à l'adresse du Fournisseur. N.B : Modifier le titre et les détails s'ils décrivent à quoi servent ces articles — le fournisseur n'a pas intérêt à savoir ça, juste les articles."},
        {"id": 9,  "title": "Réception des offres + PV d'ouverture technique",
         "desc": "Le fournisseur doit envoyer l'offre technique et commerciale avant ou le jour du délai. Transférer l'offre technique au service utilisateur pour étude de conformité technique. Le SU doit envoyer le rapport technique signé et cacheté + PV d'ouverture technique."},
        {"id": 10, "title": "Réception du PV d'OT et Rapport de conformité technique",
         "desc": "Après réception, envoyer le mail de l'offre commerciale du fournisseur au SU. Ensuite, rédiger le PV d'ouverture de l'OI et l'envoyer également au SU."},
        {"id": 11, "title": "Évaluation OI et relance pour OA1",
         "desc": "Réaliser une évaluation commerciale de l'OI (vérifier que les calculs du fournisseur sont cohérents avec les nôtres) et relancer le fournisseur pour OA1."},
        {"id": 12, "title": "Évaluation OA1 et relance pour OA2",
         "desc": "Transférer le mail de l'OA1 au SU, et relancer le fournisseur pour OA2."},
        {"id": 13, "title": "Évaluation OA2 et relance pour OA3",
         "desc": "Transférer le mail de l'OA2 au SU, et relancer le fournisseur pour OA3 en lui demandant de s'aligner sur le prix historique/Budget (le montant le moins cher entre ces deux)."},
        {"id": 14, "title": "Réception de l'offre finale et fin des négociations commerciales",
         "desc": "Demander les raisons de non-alignement si c'est le cas, conclure les négociations commerciales et envoyer l'OA3 au SU."},
        {"id": 15, "title": "Rédiger le Rapport de Binôme",
         "desc": "Rédiger le rapport de binôme, envoyer pour signature au SU et par notre direction avant CM."},
        {"id": 16, "title": "Planifier en CM et Adjudication",
         "desc": "Planifier le dossier par adjudication avec Rapport de binôme en PJ par mail, envoyer au chef de division + Planifier sur le CMCO dans NAS."},
        {"id": 17, "title": "Adjudication et rédaction du rapport de CM",
         "desc": "Rédiger le rapport de CM pour adjudication de ce dossier."},
        {"id": 18, "title": "Fiche de décision d'ED",
         "desc": "Fiche de décision d'entente directe, à ajouter dans le dossier."},
        {"id": 19, "title": "Attente de l'OK et Création du BC sur Ariba",
         "desc": "Après réception de l'OK Vert par mail, l'imprimer et garder dans le dossier, et créer le BC sur Ariba pour être envoyé au fournisseur et clôturer le dossier."},
    ],
    "CR": [
        {"id": 1,  "title": "Réception de la PR sur Ariba",
         "desc": "Vérifier que la PR soit une CR et contrôler les pièces jointes (comme le CPS)."},
        {"id": 2,  "title": "Demander le BOQ et les spécifications techniques",
         "desc": "Si ces deux documents ne sont pas joints sur Ariba, les demander par mail au SU et à sa hiérarchie."},
        {"id": 3,  "title": "Rédiger le PV1 de binôme",
         "desc": "Rédiger, vérifier et envoyer le PV1 au SU pour signature et retour."},
        {"id": 4,  "title": "Lire, vérifier et modifier le CPS — le transmettre pour avis du SU",
         "desc": "Bien lire le CPS et vérifier le contenu, ajouter la page de garde et les commentaires nécessaires au SU, puis le transmettre pour avis et retour."},
        {"id": 5,  "title": "Envoi du CPS final pour validation juridique + Réception PV1",
         "desc": "Dépôt du CPS sur la plateforme 'Galaxy' pour validation juridique et réception du PV1 signé."},
        {"id": 6,  "title": "Lancer la consultation aux fournisseurs du panel",
         "desc": "Par emails, en utilisant la copie cachée (Bcc), avec la hiérarchie en copie."},
        {"id": 7,  "title": "Dépôt des dossiers par mails séparés + Demande des raisons de non-participation",
         "desc": "Demander aux fournisseurs non-soumissionnaires leurs raisons de non-participation. Justifier si on a des adresses mail erronées."},
        {"id": 8,  "title": "Transmettre les raisons de non participation au SU et avoir leur OK pour continuer le processus",
         "desc": "Mail standard et joigné les réponses de non participations (copier les mails des sociétés)."},
        {"id": 9,  "title": "Envoyer les Mails techniques des sociétés soumissionnaires au SU et demander d'accusé leur récéption",
         "desc": "Demander l'accusé de récéption du SU puis Demander les mots de passes techniques aux soumissionnaires."},
        {"id": 10, "title": "Transferer les mails des offres techniques au SU (Avec Mots de passes)",
         "desc": "Envoyer les mails des offres techniques en PJ avec les Mots de passes communiqués au SU."},
        {"id": 11, "title": "Rédiger le PV d'OT + Demander le Rapport de conformité technique",
         "desc": "PV d'OT a envoyer et attente du rapport de conformité technique du SU."},
        {"id": 12, "title": "Ecarter les societés Non Conformes selon le Rapport + Envoyer les offeres commerciales",
         "desc": "Envoyer les offres financiers au SU des societés conformes et rédiger le PV d'Ouverture et Evalution commerciale."},
        {"id": 13, "title": "Evaluer les OI + Demander OA1 et evaluer selon la procédure",
         "desc": "Relancer les 3 premier moins disant + le 4ème si il presente un écart < 15% ."},
        {"id": 14, "title": "Evaluer les OA1 + Demander OA2 et evaluer selon la procédure",
         "desc": "Relancer le premier moins disant + le 2ème si il presente un écart < 5% ."},
        {"id": 15, "title": "Evaluer les OA2 + Demander OA3",
         "desc": "Conclure les négociations commerciales et relancer seulement le moins disant."},
        {"id": 16, "title": "Rédiger le Rapport de Binôme",
         "desc": "Rédiger le rapport de binôme final, envoyer pour signature au SU et à notre direction avant CM."},
        {"id": 17, "title": "Planifier en CM et Adjudication",
         "desc": "Planifier le dossier par adjudication avec rapport de binôme en PJ, envoyer au chef de division et planifier sur le CMCO dans NAS."},
        {"id": 18, "title": "Adjudication et rédaction du rapport de CM",
         "desc": "Rédiger le rapport de CM pour adjudication du dossier."},
        {"id": 19, "title": "Attente de l'OK et Création du BC sur Ariba",
         "desc": "Après réception de l'OK Vert par mail, l'imprimer et garder dans le dossier, et créer le BC sur Ariba pour être envoyé au fournisseur et clôturer le dossier."},
        {"id": 20, "title": "Clôture et archivage du dossier",
         "desc": "Archiver l'ensemble des documents du dossier (PV, rapports, offres, BC) et clôturer le dossier sur Ariba."},
    ],
    "COU": [
        {"id": 1, "title": "Publication de l'avis d'appel d'offres",
         "desc": "Publier l'avis d'appel d'offres sur les plateformes officielles et dans les journaux habilités conformément à la réglementation en vigueur."},
        {"id": 2, "title": "Période de consultation",
         "desc": "Gérer la période de consultation des offres : répondre aux questions des candidats, diffuser les éventuels amendements au CPS."},
        {"id": 3, "title": "Réception et traitement des offres",
         "desc": "Collecter les offres sous pli fermé, les enregistrer et préparer la séance d'ouverture avec le PV correspondant."},
        {"id": 4, "title": "Attribution et notification",
         "desc": "Attribuer le marché au soumissionnaire retenu, notifier officiellement tous les soumissionnaires du résultat et créer le BC sur Ariba pour clôturer le dossier."},
    ],
    "REG": [
        {"id": 1,  "title": "Demande et vérification de la fiche de justification de l'ED",
         "desc": "Demander la fiche de justification de l'ED, dûment signée et cachetée par la direction du SU, et vérifier au préalable si elle est déjà disponible en pièces jointes sur Ariba."},
        {"id": 2,  "title": "Programmation du dossier en Commission de Marchés (CM)",
         "desc": "Programmer le dossier pour concertation en CM."},
        {"id": 3,  "title": "Suite à la concertation",
         "desc": "Après la concertation, obtenir l'OK pour faire aboutir le dossier ou poursuivre la procédure."},
        {"id": 4,  "title": "Rédaction et envoi du PV de la CM",
         "desc": "Rédiger le procès-verbal (PV) de la CM (pour concertation) et l'envoyer, pour signature, en réponse au mail de programmation de la CM, en plaçant le Chef de Division de la section CC en tête des destinataires."},
        {"id": 5,  "title": "Demande du BOQ",
         "desc": "Envoyer au SU un mail, en réponse au mail de notification Ariba du PR, afin de demander le BOQ."},
        {"id": 6,  "title": "Rédaction du PV de la première réunion de binôme",
         "desc": "Après réception de la réponse du SU, rédiger le procès-verbal de la première réunion de binôme."},
        {"id": 7,  "title": "Transmission du PV de la première réunion de binôme",
         "desc": "Envoyer le PV de la première réunion de binôme au SU, en mettant en copie la hiérarchie achats et la hiérarchie SU. (Hors directeurs)"},
        {"id": 8,  "title": "Lancement de négociation en se basant sur le Devis",
         "desc": "Joindre les conditions générales d'achat PDF avec le devis et envoyer le mail à l'adresse du Fournisseur pour négociation."},
        {"id": 9,  "title": "Réception et Evaluation des offres",
         "desc": "Négocier avec le FR pour obtenir des meilleurs tarifs (OA1, OA2, OA3) en se basant sur le Devis comme OI. Demander de s'aligner sur le prix historique."},
        {"id": 10, "title": "Réception de l'offre finale et fin des négociations commerciales",
         "desc": "Demander les raisons de non alignement si c'est le cas, conclure les négociations commerciales."},
        {"id": 11, "title": "Rédiger le Rapport de Binôme",
         "desc": "Rédiger le rapport de binôme, envoyer pour signature au SU et par notre direction avant CM."},
        {"id": 12, "title": "Planifier en CM et Adjudication",
         "desc": "Planifier le dossier par adjudication avec Rapport de binôme en PJ par mail, envoyer au chef de division + Planifier sur le CMCO dans NAS."},
        {"id": 13, "title": "Adjudication et rédaction du rapport de CM",
         "desc": "Rédiger le rapport de CM pour adjudication de ce dossier."},
        {"id": 14, "title": "Fiche de décision d'ED",
         "desc": "Fiche de décision d'entente directe, a ajouter dans le dossier."},
        {"id": 15, "title": "Attente de l'OK et Création du BC sur Ariba",
         "desc": "Après réception de l'OK Vert par mail, l'imprimer et garder dans le dossier, et créer le BC sur Ariba pour être envoyer au FR et clôturer le dossier."},
    ],
    "Hybride": [
        {"id": 1, "title": "Entrer la première étape",
         "desc": "Première étape personnalisée du processus Hybride."},
    ],
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def compute_progress(tasks: dict) -> int:
    if not tasks:
        return 0
    completed = sum(1 for t in tasks.values() if t.get("done"))
    return round((completed / len(tasks)) * 100)

def delay_status(date_prev: str, date_reelle: str) -> str:
    """
    Returns:
      'ontime'  — réelle <= prév
      'warning' — réelle entre 1 et 5 jours après prév
      'late'    — réelle > 5 jours après prév
      ''        — données manquantes
    """
    if not date_prev or not date_reelle:
        return ""
    try:
        dp = date.fromisoformat(date_prev)
        dr = date.fromisoformat(date_reelle)
        delta = (dr - dp).days
        if delta <= 0:
            return "ontime"
        elif delta <= 5:
            return "warning"
        else:
            return "late"
    except ValueError:
        return ""

def calculate_processing_time(tasks: dict, created_date: str) -> dict:
    """
    Calculate total processing time in days from created_date to last completed step.
    Returns: { "days": int, "weeks": float, "exceeded": bool, "max_weeks": int }
    """
    if not tasks or not created_date:
        return {"days": 0, "weeks": 0, "exceeded": False, "max_weeks": 0}
    
    # Find last task with date_reelle
    last_completion = None
    for task in tasks.values():
        if task.get("date_reelle"):
            try:
                dr = date.fromisoformat(task["date_reelle"])
                if not last_completion or dr > last_completion:
                    last_completion = dr
            except ValueError:
                continue
    
    if not last_completion:
        return {"days": 0, "weeks": 0, "exceeded": False, "max_weeks": 0}
    
    try:
        start_date = date.fromisoformat(created_date)
        total_days = (last_completion - start_date).days
        total_weeks = round(total_days / 7, 1)
        return {
            "days": total_days,
            "weeks": total_weeks,
            "exceeded": False,  # Will be set by API based on category
            "max_weeks": 0
        }
    except ValueError:
        return {"days": 0, "weeks": 0, "exceeded": False, "max_weeks": 0}

def row_to_pr(row) -> dict:
    return {
        "id":           row["id"],
        "number":       row["number"],
        "title":        row["title"],
        "category":     row["category"],
        "baseCategory": row["base_category"] or row["category"],
        "status":       row["status"],
        "createdDate":  row["created_date"],
    }

def load_tasks(conn, pr_id: str) -> dict:
    rows = conn.execute(
        "SELECT * FROM task WHERE pr_id = ? ORDER BY CAST(task_id AS INTEGER)",
        (pr_id,)
    ).fetchall()
    return {
        str(r["task_id"]): {
            "title":       r["title"] or "",
            "desc":        r["description"] or "",
            "done":        bool(r["done"]),
            "date_prev":   r["date_prev"] or "",
            "date_reelle": r["date_reelle"] or "",
            "note":        r["note"] or "",
            "delay":       delay_status(r["date_prev"], r["date_reelle"]),
        }
        for r in rows
    }

def count_late_steps_for_pr(tasks: dict) -> dict:
    """Returns counts of warning and late steps."""
    warning = sum(1 for t in tasks.values() if t.get("delay") == "warning")
    late    = sum(1 for t in tasks.values() if t.get("delay") == "late")
    return {"warning": warning, "late": late}

def calculate_kpi_delay(pr_data, tasks: dict) -> dict:
    """
    Calculate processing delay in weeks for all PR types.
    
    Logic: Time from FIRST completed step to LAST completed step (regardless of category)
    When status = "cloturé", the end date is the last step completion
    When status != "cloturé", calculate from first step to today
    
    Returns: { "delay_days": int, "delay_weeks": float, "start_date": str, "end_date": str }
    """
    status = pr_data.get("status", "")
    
    if not tasks:
        return {"delay_days": 0, "delay_weeks": 0, "start_date": "", "end_date": "", "status": status}
    
    try:
        # Find first completed step date
        start_date = None
        for task_id in sorted(tasks.keys(), key=lambda x: int(x)):
            task = tasks[task_id]
            if task.get("date_reelle"):
                start_date = date.fromisoformat(task["date_reelle"])
                break
        
        # Find last completed step date
        end_date = None
        for task_id in sorted(tasks.keys(), key=lambda x: int(x), reverse=True):
            task = tasks[task_id]
            if task.get("date_reelle"):
                end_date = date.fromisoformat(task["date_reelle"])
                break
        
        # If no completed steps, return 0
        if not start_date or not end_date:
            return {"delay_days": 0, "delay_weeks": 0, "start_date": "", "end_date": "", "status": status}
        
        delay_days = (end_date - start_date).days
        delay_weeks = round(delay_days / 7, 1)
        
        return {
            "delay_days": max(0, delay_days),
            "delay_weeks": max(0, delay_weeks),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "status": status
        }
    except (ValueError, KeyError):
        return {"delay_days": 0, "delay_weeks": 0, "start_date": "", "end_date": "", "status": status}

# ─── ROUTES ─────────────────────────────────��─────────────────────────────────

@app.route("/")
def index():
    conn = get_db()
    rows = conn.execute("SELECT * FROM pr").fetchall()
    total    = len(rows)
    cloturee = sum(1 for r in rows if r["status"] == "cloturee")
    en_cours = sum(1 for r in rows if r["status"] == "en-cours")
    blockee  = sum(1 for r in rows if r["status"] == "blockee")
    annulee  = sum(1 for r in rows if r["status"] == "annulee")

    total_prog = 0
    total_late = 0
    total_warning = 0
    for r in rows:
        tasks = load_tasks(conn, r["id"])
        total_prog += compute_progress(tasks)
        counts = count_late_steps_for_pr(tasks)
        total_late    += counts["late"]
        total_warning += counts["warning"]

    avg_prog = round(total_prog / total, 1) if total else 0
    conn.close()

    stats = dict(
        total=total, cloturee=cloturee, en_cours=en_cours,
        blockee=blockee, annulee=annulee, avg_prog=avg_prog,
        total_late=total_late, total_warning=total_warning
    )
    return render_template("index.html", stats=stats)


# ── PR CRUD ──────────────��────────────────────────────────────────────────────

@app.route("/api/pr", methods=["GET"])
def get_all_pr():
    conn = get_db()
    q = request.args.get("q", "").lower()
    rows = conn.execute("SELECT * FROM pr ORDER BY created_date DESC").fetchall()
    result = []
    for r in rows:
        base_cat = r["base_category"] or r["category"]
        if q and q not in str(r["number"]).lower() \
             and q not in r["title"].lower() \
             and q not in r["category"].lower() \
             and q not in base_cat.lower():
            continue
        pr = row_to_pr(r)
        tasks = load_tasks(conn, r["id"])
        pr["progress"]        = compute_progress(tasks)
        pr["completed_tasks"] = sum(1 for t in tasks.values() if t.get("done"))
        pr["total_tasks"]     = len(tasks)
        counts = count_late_steps_for_pr(tasks)
        pr["late_steps"]    = counts["late"]
        pr["warning_steps"] = counts["warning"]
        
        # Add processing time info — use base_category for limits lookup
        proc_time = calculate_processing_time(tasks, r["created_date"])
        pr["processing_days"]  = proc_time["days"]
        pr["processing_weeks"] = proc_time["weeks"]
        max_weeks = PROCESSING_LIMITS.get(base_cat, {}).get("max_weeks", 0)
        pr["max_weeks"] = max_weeks
        pr["exceeded"] = proc_time["weeks"] > max_weeks if max_weeks > 0 else False
        
        result.append(pr)
    conn.close()
    return jsonify(result)


@app.route("/api/pr", methods=["POST"])
def create_pr():
    body     = request.json
    number   = body.get("number","").strip()
    title    = body.get("title","").strip()
    category = body.get("category","")
    pr_date  = body.get("prDate","")

    if not all([number, title, category, pr_date]):
        return jsonify({"error": "Tous les champs sont requis"}), 400
    if category not in STEPS_DATA:
        return jsonify({"error": "Catégorie invalide"}), 400

    pr_id = f"PR-{number}-{datetime.now().strftime('%f')}"
    conn  = get_db()
    conn.execute(
        "INSERT INTO pr (id, number, title, category, base_category, status, created_date) VALUES (?,?,?,?,?,?,?)",
        (pr_id, number, title, category, category, "en-cours", pr_date)
    )
    for s in STEPS_DATA[category]:
        conn.execute(
            "INSERT INTO task (pr_id, task_id, title, description, done, date_prev, date_reelle, note) VALUES (?,?,?,?,0,'','','')",
            (pr_id, str(s["id"]), s["title"], s["desc"])
        )
    # Seed default document checklist for ED / CR / COU / REG
    seed_pr_docs(conn, pr_id, category)
    conn.commit()
    conn.close()
    return jsonify({"id": pr_id, "message": "PR créée avec succès"}), 201


@app.route("/api/pr/<pr_id>", methods=["GET"])
def get_pr(pr_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM pr WHERE id = ?", (pr_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "PR introuvable"}), 404
    pr = row_to_pr(row)
    pr["baseCategory"] = row["base_category"] or row["category"]
    tasks = load_tasks(conn, pr_id)
    pr["tasks"]    = tasks
    pr["progress"] = compute_progress(tasks)
    conn.close()
    return jsonify(pr)


@app.route("/api/pr/<pr_id>", methods=["PUT"])
def update_pr(pr_id):
    conn = get_db()
    row = conn.execute("SELECT id FROM pr WHERE id = ?", (pr_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "PR introuvable"}), 404
    body = request.json
    fields = []
    values = []
    mapping = {"number":"number","title":"title","category":"category",
               "status":"status","createdDate":"created_date"}
    for k, col in mapping.items():
        if k in body:
            fields.append(f"{col} = ?")
            values.append(body[k])
    if fields:
        values.append(pr_id)
        conn.execute(f"UPDATE pr SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()
    return jsonify({"message": "PR mise à jour"})


@app.route("/api/pr/<pr_id>", methods=["DELETE"])
def delete_pr(pr_id):
    conn = get_db()
    row = conn.execute("SELECT id FROM pr WHERE id = ?", (pr_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "PR introuvable"}), 404
    conn.execute("DELETE FROM task WHERE pr_id = ?", (pr_id,))
    conn.execute("DELETE FROM pr WHERE id = ?",      (pr_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "PR supprimée"})


# ── TASK (checklist) ──────────────────────────────────────────────────────────

@app.route("/api/pr/<pr_id>/task/<task_id>", methods=["PATCH"])
def update_task(pr_id, task_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM task WHERE pr_id = ? AND task_id = ?", (pr_id, task_id)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Tâche introuvable"}), 404

    body   = request.json
    fields = []
    values = []
    allowed = {"done": "done", "date_prev": "date_prev",
               "date_reelle": "date_reelle", "note": "note"}
    for k, col in allowed.items():
        if k in body:
            val = body[k]
            if col == "done":
                val = 1 if val else 0
            fields.append(f"{col} = ?")
            values.append(val)
    if fields:
        values += [pr_id, task_id]
        conn.execute(f"UPDATE task SET {', '.join(fields)} WHERE pr_id = ? AND task_id = ?", values)
        conn.commit()

    tasks    = load_tasks(conn, pr_id)
    progress = compute_progress(tasks)
    counts   = count_late_steps_for_pr(tasks)
    # Return the updated task delay status too
    updated_task = tasks.get(task_id, {})
    conn.close()
    return jsonify({
        "progress":      progress,
        "late_steps":    counts["late"],
        "warning_steps": counts["warning"],
        "delay":         updated_task.get("delay", ""),
    })


# ── LOST DAYS ─────────────────────────────────────────────────────────────────

@app.route("/api/pr/<pr_id>/lost-days", methods=["POST"])
def set_lost_days(pr_id):
    """Update lost days for a PR and return updated delay calculations."""
    conn = get_db()
    row = conn.execute("SELECT id FROM pr WHERE id = ?", (pr_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "PR introuvable"}), 404
    
    lost_days = request.json.get("lost_days", 0)
    try:
        lost_days = int(lost_days)
        if lost_days < 0:
            lost_days = 0
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Jours perdus invalides"}), 400
    
    conn.execute("UPDATE pr SET lost_days = ? WHERE id = ?", (lost_days, pr_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Jours perdus mis à jour", "lost_days": lost_days})


# ── STATUS ────────────────────────────────────────────────────────────────────

@app.route("/api/pr/<pr_id>/status", methods=["PATCH"])
def set_status(pr_id):
    conn  = get_db()
    row   = conn.execute("SELECT id FROM pr WHERE id = ?", (pr_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "PR introuvable"}), 404
    status = request.json.get("status")
    valid  = ["en-cours", "cloturee", "blockee", "annulee"]
    if status not in valid:
        conn.close()
        return jsonify({"error": "Statut invalide"}), 400
    conn.execute("UPDATE pr SET status = ? WHERE id = ?", (status, pr_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Statut mis à jour"})


# ── EDIT HYBRID STEP ──────────────────────────────────────────────────────────

@app.route("/api/pr/<pr_id>/step/<step_id>", methods=["PUT"])
def update_hybrid_step(pr_id, step_id):
    """Update a step's title and description."""
    conn = get_db()
    row = conn.execute("SELECT * FROM pr WHERE id = ?", (pr_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "PR introuvable"}), 404
    
    title = request.json.get("title", "").strip()
    desc = request.json.get("desc", "").strip()
    
    if not title:
        conn.close()
        return jsonify({"error": "Le titre est requis"}), 400
    
    # Update task
    conn.execute(
        "UPDATE task SET title = ?, description = ? WHERE pr_id = ? AND task_id = ?",
        (title, desc, pr_id, step_id)
    )
    conn.commit()
    conn.close()
    
    return jsonify({
        "task_id": step_id,
        "title": title,
        "desc": desc,
        "success": True
    })


# ── ADD HYBRID STEP ───────────────────────────────────────────────────────────

@app.route("/api/pr/<pr_id>/add-step", methods=["POST"])
def add_hybrid_step(pr_id):
    """Add a new step to a Hybrid PR."""
    conn = get_db()
    row = conn.execute("SELECT * FROM pr WHERE id = ?", (pr_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "PR introuvable"}), 404
    
    base_cat = row["base_category"] or row["category"]
    if base_cat != "Hybride":
        conn.close()
        return jsonify({"error": "Cette PR n'est pas de type Hybride"}), 400
    
    # Get current steps
    tasks = load_tasks(conn, pr_id)
    
    # Find next task ID
    max_id = max([int(task_id) for task_id in tasks.keys()]) if tasks else 0
    new_task_id = str(max_id + 1)
    
    title = request.json.get("title", "").strip()
    desc = request.json.get("desc", "").strip()
    
    if not title:
        conn.close()
        return jsonify({"error": "Le titre est requis"}), 400
    
    # Insert new task
    conn.execute("""
        INSERT INTO task (pr_id, task_id, title, description, date_prev, date_reelle, done)
        VALUES (?, ?, ?, ?, '', '', 0)
    """, (pr_id, new_task_id, title, desc))
    conn.commit()
    conn.close()
    
    return jsonify({
        "task_id": new_task_id,
        "title": title,
        "desc": desc,
        "success": True
    })


# ���─ STEPS REFERENCE ───────────────────────────────────────────────────────────

@app.route("/api/steps/<category>")
def get_steps(category):
    if category not in STEPS_DATA:
        return jsonify({"error": "Catégorie invalide"}), 404
    return jsonify(STEPS_DATA[category])


# ── ALERTS API ──────────────────────────────────────────────────────���─────────

@app.route("/api/alerts")
def get_alerts():
    """Returns all PR/steps that are late or in warning state."""
    conn  = get_db()
    rows  = conn.execute("SELECT * FROM pr WHERE status = 'en-cours'").fetchall()
    alerts = []
    for r in rows:
        tasks  = load_tasks(conn, r["id"])
        for tid, task in tasks.items():
            if task["delay"] in ("warning", "late") and not task["done"]:
                alerts.append({
                    "pr_id":       r["id"],
                    "pr_number":   r["number"],
                    "pr_title":    r["title"],
                    "task_id":     tid,
                    "task_title":  task["title"],
                    "date_prev":   task["date_prev"],
                    "date_reelle": task["date_reelle"],
                    "delay":       task["delay"],
                })
    conn.close()
    alerts.sort(key=lambda a: (0 if a["delay"] == "late" else 1))
    return jsonify(alerts)


# ── EXPORT EXCEL ──────────────────────────────────────────────────────────────

@app.route("/api/export")
def export_excel():
    conn      = get_db()
    date_from = request.args.get("from", "")
    date_to   = request.args.get("to",   "")

    wb        = openpyxl.Workbook()
    ws_ov     = wb.active
    ws_ov.title = "Vue d'ensemble"

    red_fill    = PatternFill("solid", fgColor="C0392B")
    grey_fill   = PatternFill("solid", fgColor="F2F2F2")
    white_fill  = PatternFill("solid", fgColor="FFFFFF")
    green_fill  = PatternFill("solid", fgColor="D5F5E3")
    orange_fill = PatternFill("solid", fgColor="FDEBD0")
    late_fill   = PatternFill("solid", fgColor="FADBD8")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    normal_font = Font(size=10)
    center      = Alignment(horizontal="center", vertical="center")
    thin        = Side(style="thin", color="DDDDDD")
    border      = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers_ov = ["N° PR", "Titre", "Catégorie", "Statut", "Date demande",
                  "Progression (%)", "Étapes complétées", "Total étapes",
                  "Étapes en retard", "Étapes à risque"]
    for col, h in enumerate(headers_ov, 1):
        cell = ws_ov.cell(row=1, column=col, value=h)
        cell.font = header_font; cell.fill = red_fill
        cell.alignment = center; cell.border = border

    row_idx = 2
    rows = conn.execute("SELECT * FROM pr ORDER BY created_date DESC").fetchall()
    for r in rows:
        if date_from and r["created_date"] < date_from: continue
        if date_to   and r["created_date"] > date_to:   continue
        tasks     = load_tasks(conn, r["id"])
        completed = sum(1 for t in tasks.values() if t.get("done"))
        progress  = compute_progress(tasks)
        counts    = count_late_steps_for_pr(tasks)
        fill      = grey_fill if row_idx % 2 == 0 else white_fill
        row_data  = [r["number"], r["title"], r["category"], r["status"],
                     r["created_date"], progress, completed, len(tasks),
                     counts["late"], counts["warning"]]
        for col, val in enumerate(row_data, 1):
            cell = ws_ov.cell(row=row_idx, column=col, value=val)
            cell.font = normal_font; cell.fill = fill
            cell.alignment = center if col != 2 else Alignment(vertical="center")
            cell.border = border
        row_idx += 1

    col_widths_ov = [12, 35, 14, 14, 16, 18, 20, 14, 18, 18]
    for i, w in enumerate(col_widths_ov, 1):
        ws_ov.column_dimensions[get_column_letter(i)].width = w
    ws_ov.row_dimensions[1].height = 22

    # One sheet per PR with full task details
    for r in rows:
        if date_from and r["created_date"] < date_from: continue
        if date_to   and r["created_date"] > date_to:   continue
        sheet_name = f"PR-{r['number']}"[:31]
        ws = wb.create_sheet(title=sheet_name)
        headers_pr = ["N°", "Titre de l'étape", "Description",
                      "Complétée", "Date prévisionnelle", "Date réelle",
                      "Délai", "Notes"]
        for col, h in enumerate(headers_pr, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font; cell.fill = red_fill
            cell.alignment = center; cell.border = border

        tasks = load_tasks(conn, r["id"])
        for row_i, (tid, task) in enumerate(tasks.items(), 2):
            delay = task.get("delay", "")
            if delay == "ontime":
                row_fill = green_fill
            elif delay == "warning":
                row_fill = orange_fill
            elif delay == "late":
                row_fill = late_fill
            else:
                row_fill = grey_fill if row_i % 2 == 0 else white_fill

            delay_labels = {"ontime": "Dans les délais", "warning": "Risque retard",
                            "late": "En retard", "": "—"}
            row_data = [tid, task.get("title"), task.get("desc"),
                        "Oui" if task.get("done") else "Non",
                        task.get("date_prev",""), task.get("date_reelle",""),
                        delay_labels.get(delay, "—"), task.get("note","")]
            for col, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_i, column=col, value=val)
                cell.font = normal_font; cell.fill = row_fill
                cell.border = border
                cell.alignment = center if col in [1, 4, 5, 6, 7] \
                    else Alignment(vertical="center", wrap_text=True)

        for i, w in enumerate([6, 32, 45, 12, 20, 20, 18, 40], 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    conn.close()
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"PR_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(output,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=filename)


# ── EXPORT KPI EXCEL ─────────────────────────────────────────────────────────

@app.route("/api/export-kpi")
def export_kpi_excel():
    """Generate a professional KPI Excel report with processing delays."""
    conn = get_db()
    category_filter = request.args.get("category", "")

    wb = openpyxl.Workbook()

    # ── Color palette ──
    brand_dark   = "1B2A4A"
    brand_mid    = "2C4A7C"
    brand_accent = "3B82F6"
    white        = "FFFFFF"
    light_bg     = "F8FAFC"
    border_color = "E2E8F0"
    green_bg     = "DCFCE7"
    green_txt    = "166534"
    orange_bg    = "FEF3C7"
    orange_txt   = "92400E"
    red_bg       = "FEE2E2"
    red_txt      = "991B1B"
    grey_bg      = "F1F5F9"
    grey_txt     = "64748B"

    # ── Shared styles ──
    thin_border = Border(
        left=Side(style="thin", color=border_color),
        right=Side(style="thin", color=border_color),
        top=Side(style="thin", color=border_color),
        bottom=Side(style="thin", color=border_color),
    )
    header_font      = Font(bold=True, color=white, size=11, name="Calibri")
    header_fill      = PatternFill("solid", fgColor=brand_dark)
    subheader_font   = Font(bold=True, color=brand_dark, size=10, name="Calibri")
    subheader_fill   = PatternFill("solid", fgColor="E2E8F0")
    normal_font      = Font(size=10, name="Calibri")
    bold_font        = Font(bold=True, size=10, name="Calibri")
    title_font       = Font(bold=True, size=16, color=brand_dark, name="Calibri")
    subtitle_font    = Font(size=11, color=grey_txt, name="Calibri")
    kpi_value_font   = Font(bold=True, size=22, color=brand_dark, name="Calibri")
    kpi_label_font   = Font(size=9, color=grey_txt, name="Calibri")
    center_align     = Alignment(horizontal="center", vertical="center")
    left_align       = Alignment(horizontal="left", vertical="center")
    wrap_align       = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # ── Fetch all PR data ──
    rows = conn.execute("SELECT * FROM pr ORDER BY created_date DESC").fetchall()
    kpi_records = []
    for row in rows:
        base_cat = row["base_category"] or row["category"]
        if category_filter and base_cat != category_filter:
            continue
        pr_data = row_to_pr(row)
        tasks = load_tasks(conn, row["id"])
        kpi = calculate_kpi_delay(pr_data, tasks)
        counts = count_late_steps_for_pr(tasks)
        progress = compute_progress(tasks)
        completed = sum(1 for t in tasks.values() if t.get("done"))

        max_weeks = PROCESSING_LIMITS.get(base_cat, {}).get("max_weeks", 0)
        if row["status"] == "cloturee" and max_weeks > 0:
            if kpi["delay_weeks"] <= max_weeks:
                indicator = "A temps"
            else:
                indicator = f"Depassé (+{round(kpi['delay_weeks'] - max_weeks, 1)}s)"
        elif row["status"] == "cloturee":
            indicator = "Cloturé"
        else:
            indicator = "En cours"

        kpi_records.append({
            "number":        row["number"],
            "title":         row["title"],
            "category":      row["category"],
            "base_category": base_cat,
            "status":        row["status"],
            "created_date":  row["created_date"],
            "delay_weeks":   kpi["delay_weeks"],
            "delay_days":    kpi["delay_days"],
            "start_date":    kpi["start_date"],
            "end_date":      kpi["end_date"],
            "max_weeks":     max_weeks,
            "indicator":     indicator,
            "progress":      progress,
            "completed":     completed,
            "total_tasks":   len(tasks),
            "late_steps":    counts["late"],
            "warning_steps": counts["warning"],
            "tasks":         tasks,
        })

    # ═══════════════════════════════════════════════════════════════════════
    #  SHEET 1 — Tableau de Bord KPI
    # ═══════════════════════════════════════════════════════════════════════
    ws = wb.active
    ws.title = "Tableau de Bord KPI"
    ws.sheet_properties.tabColor = brand_accent

    # Title block
    ws.merge_cells("A1:H1")
    cell = ws.cell(row=1, column=1, value="RAPPORT KPI — Délais de Traitement")
    cell.font = title_font
    cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 40

    ws.merge_cells("A2:H2")
    filter_label = f"Filtre : {category_filter}" if category_filter else "Toutes catégories"
    cell = ws.cell(row=2, column=1, value=f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — {filter_label}")
    cell.font = subtitle_font
    ws.row_dimensions[2].height = 22

    # ── Summary KPI cards (row 4) ──
    total_prs     = len(kpi_records)
    closed_prs    = [r for r in kpi_records if r["status"] == "cloturee"]
    in_progress   = [r for r in kpi_records if r["status"] == "en-cours"]
    on_time_prs   = [r for r in closed_prs if r["indicator"] == "A temps"]
    exceeded_prs  = [r for r in closed_prs if r["indicator"].startswith("Depassé")]
    avg_delay     = round(sum(r["delay_weeks"] for r in closed_prs) / len(closed_prs), 1) if closed_prs else 0
    total_late    = sum(r["late_steps"] for r in kpi_records)
    total_warning = sum(r["warning_steps"] for r in kpi_records)

    kpi_cards = [
        ("Total PR",           str(total_prs),         brand_dark),
        ("Clôturées",          str(len(closed_prs)),   "16A34A"),
        ("En Cours",           str(len(in_progress)),  "EAB308"),
        ("À Temps",            str(len(on_time_prs)),  "16A34A"),
        ("Dépassées",          str(len(exceeded_prs)), "DC2626"),
        ("Délai Moyen (sem.)", str(avg_delay),         brand_accent),
        ("Étapes en Retard",   str(total_late),        "DC2626"),
        ("Étapes à Risque",    str(total_warning),     "F59E0B"),
    ]

    row_idx = 4
    for col_i, (label, value, color) in enumerate(kpi_cards, 1):
        # Value cell
        c = ws.cell(row=row_idx, column=col_i, value=value)
        c.font = Font(bold=True, size=18, color=color, name="Calibri")
        c.alignment = center_align
        c.fill = PatternFill("solid", fgColor=light_bg)
        c.border = thin_border
        # Label cell
        c = ws.cell(row=row_idx + 1, column=col_i, value=label)
        c.font = kpi_label_font
        c.alignment = center_align
        c.fill = PatternFill("solid", fgColor=light_bg)
        c.border = thin_border

    ws.row_dimensions[row_idx].height = 36
    ws.row_dimensions[row_idx + 1].height = 22

    # ── Separator ──
    row_idx = 7

    # ── Detail Table Header ──
    headers = [
        "N° PR", "Titre", "Type", "Statut",
        "Date Demande", "Délai (sem.)", "Délai Max (sem.)",
        "Progression", "Étapes Retard", "Étapes Risque", "Indicateur"
    ]
    for col_i, h in enumerate(headers, 1):
        c = ws.cell(row=row_idx, column=col_i, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center_align
        c.border = thin_border
    ws.row_dimensions[row_idx].height = 28

    # ── Detail Table Rows ──
    row_idx = 8
    for rec in kpi_records:
        is_even = (row_idx % 2 == 0)
        row_fill = PatternFill("solid", fgColor=light_bg) if is_even else PatternFill("solid", fgColor=white)

        status_labels = {
            "en-cours": "En Cours", "cloturee": "Clôturée",
            "blockee": "Bloquée", "annulee": "Annulée"
        }

        row_data = [
            f"PR #{rec['number']}",
            rec["title"],
            rec["category"],
            status_labels.get(rec["status"], rec["status"]),
            rec["created_date"],
            rec["delay_weeks"],
            rec["max_weeks"] if rec["max_weeks"] > 0 else "N/A",
            f"{rec['progress']}%",
            rec["late_steps"],
            rec["warning_steps"],
            rec["indicator"],
        ]

        for col_i, val in enumerate(row_data, 1):
            c = ws.cell(row=row_idx, column=col_i, value=val)
            c.font = normal_font
            c.border = thin_border
            c.fill = row_fill
            c.alignment = center_align if col_i != 2 else wrap_align

        # Color the indicator cell
        ind_cell = ws.cell(row=row_idx, column=11)
        if rec["indicator"] == "A temps":
            ind_cell.fill = PatternFill("solid", fgColor=green_bg)
            ind_cell.font = Font(bold=True, size=10, color=green_txt, name="Calibri")
        elif rec["indicator"].startswith("Depassé"):
            ind_cell.fill = PatternFill("solid", fgColor=red_bg)
            ind_cell.font = Font(bold=True, size=10, color=red_txt, name="Calibri")
        elif rec["indicator"] == "En cours":
            ind_cell.fill = PatternFill("solid", fgColor=orange_bg)
            ind_cell.font = Font(bold=True, size=10, color=orange_txt, name="Calibri")

        # Color late/warning counts
        if rec["late_steps"] > 0:
            late_cell = ws.cell(row=row_idx, column=9)
            late_cell.fill = PatternFill("solid", fgColor=red_bg)
            late_cell.font = Font(bold=True, size=10, color=red_txt, name="Calibri")
        if rec["warning_steps"] > 0:
            warn_cell = ws.cell(row=row_idx, column=10)
            warn_cell.fill = PatternFill("solid", fgColor=orange_bg)
            warn_cell.font = Font(bold=True, size=10, color=orange_txt, name="Calibri")

        row_idx += 1

    # Column widths
    col_widths = [12, 40, 14, 14, 16, 16, 18, 14, 16, 16, 20]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ═══════════════════════════════════════════════════════════════════════
    #  SHEET 2 — Détail par Catégorie
    # ═══════════════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet(title="Analyse par Catégorie")
    ws2.sheet_properties.tabColor = "16A34A"

    ws2.merge_cells("A1:F1")
    c = ws2.cell(row=1, column=1, value="Analyse par Catégorie de Procédure")
    c.font = title_font
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws2.row_dimensions[1].height = 36

    cat_headers = ["Catégorie", "Total PR", "Clôturées", "En Cours", "Délai Moyen (sem.)", "Délai Max Réglementaire (sem.)"]
    for col_i, h in enumerate(cat_headers, 1):
        c = ws2.cell(row=3, column=col_i, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center_align
        c.border = thin_border
    ws2.row_dimensions[3].height = 28

    categories_in_data = {}
    for rec in kpi_records:
        bc = rec["base_category"]
        if bc not in categories_in_data:
            categories_in_data[bc] = {"total": 0, "closed": 0, "in_progress": 0, "delays": []}
        categories_in_data[bc]["total"] += 1
        if rec["status"] == "cloturee":
            categories_in_data[bc]["closed"] += 1
            categories_in_data[bc]["delays"].append(rec["delay_weeks"])
        elif rec["status"] == "en-cours":
            categories_in_data[bc]["in_progress"] += 1

    r_idx = 4
    for cat_name, cat_data in sorted(categories_in_data.items()):
        avg_d = round(sum(cat_data["delays"]) / len(cat_data["delays"]), 1) if cat_data["delays"] else 0
        max_w = PROCESSING_LIMITS.get(cat_name, {}).get("max_weeks", "N/A")
        is_even = (r_idx % 2 == 0)
        row_fill = PatternFill("solid", fgColor=light_bg) if is_even else PatternFill("solid", fgColor=white)

        vals = [cat_name, cat_data["total"], cat_data["closed"], cat_data["in_progress"], avg_d, max_w]
        for col_i, val in enumerate(vals, 1):
            c = ws2.cell(row=r_idx, column=col_i, value=val)
            c.font = bold_font if col_i == 1 else normal_font
            c.alignment = center_align
            c.border = thin_border
            c.fill = row_fill
        r_idx += 1

    for i, w in enumerate([18, 12, 14, 14, 22, 28], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # ═══════════════════════════════════════════════════════════════════════
    #  SHEET 3 — Détail Étapes par PR
    # ═══════════════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet(title="Détail Étapes")
    ws3.sheet_properties.tabColor = "EAB308"

    ws3.merge_cells("A1:I1")
    c = ws3.cell(row=1, column=1, value="Détail des Étapes par PR")
    c.font = title_font
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws3.row_dimensions[1].height = 36

    step_headers = [
        "N° PR", "Titre PR", "N° Étape", "Titre Étape",
        "Complétée", "Date Prév.", "Date Réelle", "Délai", "Notes"
    ]
    for col_i, h in enumerate(step_headers, 1):
        c = ws3.cell(row=3, column=col_i, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center_align
        c.border = thin_border
    ws3.row_dimensions[3].height = 28

    r_idx = 4
    delay_labels = {"ontime": "Dans les délais", "warning": "Risque retard", "late": "En retard", "": "—"}
    for rec in kpi_records:
        for tid, task in rec["tasks"].items():
            delay = task.get("delay", "")
            is_even = (r_idx % 2 == 0)

            if delay == "ontime":
                row_fill = PatternFill("solid", fgColor=green_bg)
            elif delay == "warning":
                row_fill = PatternFill("solid", fgColor=orange_bg)
            elif delay == "late":
                row_fill = PatternFill("solid", fgColor=red_bg)
            else:
                row_fill = PatternFill("solid", fgColor=light_bg) if is_even else PatternFill("solid", fgColor=white)

            vals = [
                f"PR #{rec['number']}", rec["title"], tid, task.get("title", ""),
                "Oui" if task.get("done") else "Non",
                task.get("date_prev", ""), task.get("date_reelle", ""),
                delay_labels.get(delay, "—"), task.get("note", "")
            ]
            for col_i, val in enumerate(vals, 1):
                c = ws3.cell(row=r_idx, column=col_i, value=val)
                c.font = normal_font
                c.border = thin_border
                c.fill = row_fill
                c.alignment = center_align if col_i not in [2, 4, 9] else wrap_align
            r_idx += 1

    for i, w in enumerate([12, 35, 10, 35, 12, 16, 16, 18, 40], 1):
        ws3.column_dimensions[get_column_letter(i)].width = w

    conn.close()

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"KPI_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


# ── PROCESSING TIME LIMITS (API) ──────────────────────────────────────────────
@app.route("/api/processing-limits", methods=["GET"])
def get_processing_limits():
    return jsonify(PROCESSING_LIMITS)


# ── DOCUMENTS MANAGEMENT ──────────��───────────────────────────────────────────

@app.route("/api/documents", methods=["GET"])
def get_documents():
    conn = get_db()
    c = conn.cursor()
    docs = c.execute("SELECT * FROM document ORDER BY created_date DESC").fetchall()
    conn.close()
    return jsonify([
        {
            "id": doc[0],
            "name": doc[1],
            "status": doc[2],
            "color": doc[3],
            "done": doc[4],
            "created_date": doc[5],
        }
        for doc in docs
    ])


@app.route("/api/documents", methods=["POST"])
def create_document():
    data = request.get_json()
    doc_id = str(uuid.uuid4())
    name = data.get("name", "").strip()
    status = data.get("status", "En attente").strip()
    color = data.get("color", "#3498db").strip()
    
    if not name:
        return jsonify({"error": "Document name is required"}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO document (id, name, status, color, done, created_date) VALUES (?, ?, ?, ?, 0, ?)",
        (doc_id, name, status, color, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    return jsonify({
        "id": doc_id,
        "name": name,
        "status": status,
        "color": color,
        "done": 0,
        "created_date": datetime.now().isoformat(),
    }), 201


@app.route("/api/documents/<doc_id>", methods=["PUT"])
def update_document(doc_id):
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    
    doc = c.execute("SELECT * FROM document WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        return jsonify({"error": "Document not found"}), 404
    
    name = data.get("name", doc[1]).strip()
    status = data.get("status", doc[2]).strip()
    color = data.get("color", doc[3]).strip()
    done = data.get("done", doc[4])
    
    c.execute(
        "UPDATE document SET name = ?, status = ?, color = ?, done = ? WHERE id = ?",
        (name, status, color, done, doc_id)
    )
    conn.commit()
    conn.close()
    
    return jsonify({
        "id": doc_id,
        "name": name,
        "status": status,
        "color": color,
        "done": done,
        "created_date": doc[5],
    })


@app.route("/api/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    conn = get_db()
    c = conn.cursor()
    
    doc = c.execute("SELECT * FROM document WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        return jsonify({"error": "Document not found"}), 404
    
    c.execute("DELETE FROM document WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})


# ── PER-PR DOCUMENT CHECKLIST ────────────────────────────────────────────────

@app.route("/api/pr/<pr_id>/docs", methods=["GET"])
def get_pr_docs(pr_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM pr_doc_checklist WHERE pr_id = ? ORDER BY sort_order ASC, id ASC",
        (pr_id,)
    ).fetchall()
    conn.close()
    return jsonify([
        {"id": r["id"], "name": r["name"], "done": bool(r["done"]), "sort_order": r["sort_order"]}
        for r in rows
    ])


@app.route("/api/pr/<pr_id>/docs", methods=["POST"])
def add_pr_doc(pr_id):
    conn = get_db()
    row = conn.execute("SELECT id FROM pr WHERE id = ?", (pr_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "PR introuvable"}), 404
    name = request.json.get("name", "").strip()
    if not name:
        conn.close()
        return jsonify({"error": "Le nom est requis"}), 400
    max_order = conn.execute(
        "SELECT MAX(sort_order) FROM pr_doc_checklist WHERE pr_id = ?", (pr_id,)
    ).fetchone()[0] or 0
    doc_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO pr_doc_checklist (id, pr_id, name, done, sort_order) VALUES (?,?,?,0,?)",
        (doc_id, pr_id, name, max_order + 1)
    )
    conn.commit()
    conn.close()
    return jsonify({"id": doc_id, "name": name, "done": False, "sort_order": max_order + 1}), 201


@app.route("/api/pr/<pr_id>/docs/<doc_id>", methods=["PATCH"])
def patch_pr_doc(pr_id, doc_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM pr_doc_checklist WHERE id = ? AND pr_id = ?", (doc_id, pr_id)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Document introuvable"}), 404
    body = request.json
    fields, values = [], []
    if "done" in body:
        fields.append("done = ?"); values.append(1 if body["done"] else 0)
    if "name" in body:
        name = body["name"].strip()
        if not name:
            conn.close()
            return jsonify({"error": "Le nom est requis"}), 400
        fields.append("name = ?"); values.append(name)
    if fields:
        values += [doc_id, pr_id]
        conn.execute(f"UPDATE pr_doc_checklist SET {', '.join(fields)} WHERE id = ? AND pr_id = ?", values)
        conn.commit()
    updated = conn.execute(
        "SELECT * FROM pr_doc_checklist WHERE id = ? AND pr_id = ?", (doc_id, pr_id)
    ).fetchone()
    conn.close()
    return jsonify({"id": updated["id"], "name": updated["name"], "done": bool(updated["done"]), "sort_order": updated["sort_order"]})


@app.route("/api/pr/<pr_id>/docs/<doc_id>", methods=["DELETE"])
def delete_pr_doc(pr_id, doc_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM pr_doc_checklist WHERE id = ? AND pr_id = ?", (doc_id, pr_id)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Document introuvable"}), 404
    conn.execute("DELETE FROM pr_doc_checklist WHERE id = ? AND pr_id = ?", (doc_id, pr_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ── KPI PROCESSING DELAYS ────────────────────────────────────────────────────

@app.route("/api/kpi/processing-delays", methods=["GET"])
def get_kpi_processing_delays():
    category_filter = request.args.get("category", "")
    
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("SELECT * FROM pr ORDER BY created_date DESC").fetchall()
    
    kpi_data = []
    for row in rows:
        # Apply category filter using base_category for Hybride variants
        base_cat = row["base_category"] or row["category"]
        if category_filter and base_cat != category_filter:
            continue
        
        pr_data = row_to_pr(row)
        tasks = load_tasks(conn, row["id"])
        
        # Calculate KPI delay
        kpi = calculate_kpi_delay(pr_data, tasks)
        
        # Get lost_days from the database
        lost_days = row["lost_days"] if "lost_days" in row.keys() else 0
        
        # Calculate adjusted delay: subtract lost_days from delay_weeks
        adjusted_delay_weeks = kpi["delay_weeks"] - (lost_days / 7.0)
        adjusted_delay_weeks = round(adjusted_delay_weeks, 1)
        # Ensure delay doesn't go below 0
        if adjusted_delay_weeks < 0:
            adjusted_delay_weeks = 0
        
        kpi_data.append({
            "id": pr_data["id"],
            "number": pr_data["number"],
            "title": pr_data["title"],
            "category": pr_data["category"],
            "baseCategory": base_cat,
            "status": pr_data["status"],
            "delay_weeks": adjusted_delay_weeks,
            "delay_days": kpi["delay_days"],
            "lost_days": lost_days,
            "start_date": kpi["start_date"],
            "end_date": kpi["end_date"]
        })
    
    conn.close()
    return jsonify(kpi_data)


# ── IMPORT EXCEL ──────────────────────────────────────────────────────────────

@app.route("/api/import", methods=["POST"])
def import_excel():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400
    f = request.files["file"]
    if not f.filename.endswith(".xlsx"):
        return jsonify({"error": "Format invalide — fichier .xlsx requis"}), 400
    try:
        wb = openpyxl.load_workbook(io.BytesIO(f.read()))
        if "Vue d'ensemble" not in wb.sheetnames and "Overview" not in wb.sheetnames:
            return jsonify({"error": "Onglet 'Vue d'ensemble' introuvable"}), 400
        ws_ov = wb["Vue d'ensemble"] if "Vue d'ensemble" in wb.sheetnames else wb["Overview"]
        conn = get_db()
        imported = 0
        for row in ws_ov.iter_rows(min_row=2, values_only=True):
            if not row[0]: continue
            number, title, category, status, created_date = \
                row[0], row[1], row[2], row[3], row[4]
            if category not in STEPS_DATA: continue
            pr_id      = f"PR-{number}-imported"
            sheet_name = f"PR-{number}"[:31]
            # upsert PR
            conn.execute(
                "INSERT OR REPLACE INTO pr (id, number, title, category, base_category, status, created_date) VALUES (?,?,?,?,?,?,?)",
                (pr_id, str(number), str(title), category, category,
                 status or "en-cours", str(created_date) if created_date else "")
            )
            conn.execute("DELETE FROM task WHERE pr_id = ?", (pr_id,))
            if sheet_name in wb.sheetnames:
                ws_pr = wb[sheet_name]
                for tr in ws_pr.iter_rows(min_row=2, values_only=True):
                    if not tr[0]: continue
                    tid, ttitle, tdesc, tdone, tprev, treelle, _delay, tnote = \
                        tr[0], tr[1], tr[2], tr[3], tr[4], tr[5], tr[6] if len(tr)>6 else "", tr[7] if len(tr)>7 else ""
                    conn.execute(
                        "INSERT INTO task (pr_id,task_id,title,description,done,date_prev,date_reelle,note) VALUES (?,?,?,?,?,?,?,?)",
                        (pr_id, str(tid), ttitle or "", tdesc or "",
                         1 if tdone == "Oui" else 0,
                         str(tprev) if tprev else "", str(treelle) if treelle else "",
                         tnote or "")
                    )
            else:
                for s in STEPS_DATA[category]:
                    conn.execute(
                        "INSERT INTO task (pr_id,task_id,title,description,done,date_prev,date_reelle,note) VALUES (?,?,?,?,0,'','','')",
                        (pr_id, str(s["id"]), s["title"], s["desc"])
                    )
            imported += 1
        conn.commit()
        conn.close()
        return jsonify({"message": f"{imported} PR importée(s) avec succès", "imported": imported})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── GENERATE EMPTY DB FOR DISTRIBUTION ────────────────────────────────────────
def create_empty_db():
    """
    Creates flask_app/data/empty_pr_data.db — same schema, zero rows.
    Give this file to a colleague: they rename it to pr_data.db and place it
    in flask_app/data/ to start fresh with their own data.
    """
    empty_path = os.path.join(os.path.dirname(__file__), "data", "empty_pr_data.db")
    os.makedirs(os.path.dirname(empty_path), exist_ok=True)
    if os.path.exists(empty_path):
        return  # already exists, skip
    conn = sqlite3.connect(empty_path)
    c = conn.cursor()
    c.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS pr (
            id            TEXT PRIMARY KEY,
            number        TEXT NOT NULL,
            title         TEXT NOT NULL,
            category      TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'en-cours',
            created_date  TEXT NOT NULL,
            date_prev     TEXT NOT NULL DEFAULT '',
            date_reelle   TEXT NOT NULL DEFAULT '',
            note          TEXT NOT NULL DEFAULT '',
            custom_steps  TEXT NOT NULL DEFAULT '',
            base_category TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS task (
            pr_id       TEXT NOT NULL,
            task_id     TEXT NOT NULL,
            title       TEXT,
            description TEXT,
            done        INTEGER NOT NULL DEFAULT 0,
            date_prev   TEXT DEFAULT '',
            date_reelle TEXT DEFAULT '',
            note        TEXT DEFAULT '',
            PRIMARY KEY (pr_id, task_id),
            FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS document (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'En attente',
            color        TEXT NOT NULL DEFAULT '#D4798A',
            done         INTEGER NOT NULL DEFAULT 0,
            created_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pr_document (
            id     TEXT PRIMARY KEY,
            pr_id  TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            name   TEXT NOT NULL,
            done   INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pr_doc_checklist (
            id         TEXT PRIMARY KEY,
            pr_id      TEXT NOT NULL,
            name       TEXT NOT NULL,
            done       INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


# ─── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    create_empty_db()
    app.run(debug=True, port=5000)
