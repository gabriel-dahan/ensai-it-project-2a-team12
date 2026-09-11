"""
Script d'inspection et de visualisation de fichiers Parquet dans la console.
Utilise DuckDB pour la rapidité et Rich pour le rendu visuel.
"""

from typing import Optional
import duckdb
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Instanciation de la console Rich
console = Console()

# ==============================================================================
# CONFIGURATION : MODIFIEZ VOS CHEMINS DE FICHIERS ICI
# ==============================================================================
PARQUET_METEO = (
    "/home/onyxia/work/ensai-it-project-2a-team12/data/raw_data/meteo_france_1990_2026.parquet"
)
PARQUET_COMMUNES = (
    "/home/onyxia/work/ensai-it-project-2a-team12/data/raw_data/communes.parquet"
)


def display_parquet_summary(
    file_path: str, table_alias: str = "df", sample_size: int = 5
) -> None:
    """Affiche un résumé complet (Schéma, taille, extrait) d'un fichier Parquet."""
    try:
        con = duckdb.connect()

        # Nombre total de lignes
        nb_rows = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{file_path}')"
        ).fetchone()[0]

        # Structure / Schéma
        schema_df = con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{file_path}')"
        ).fetchdf()

        # En-tête
        console.print(
            Panel(
                f"[bold cyan]Fichier :[/bold cyan] {file_path}\n"
                f"[bold green]Nombre total de lignes :[/bold green] {nb_rows:,}".replace(
                    ",", " "
                ),
                title=f"📊 Analyse de [yellow]{table_alias}[/yellow]",
                expand=False,
            )
        )

        # Affichage du Schéma (Colonnes & Types)
        schema_table = Table(
            title="🔍 Schéma des colonnes", show_header=True, header_style="bold magenta"
        )
        schema_table.add_column("Nom de la colonne", style="bold white")
        schema_table.add_column("Type de donnée", style="green")

        for _, row in schema_df.iterrows():
            schema_table.add_row(str(row["column_name"]), str(row["column_type"]))

        console.print(schema_table)

        # Aperçu des données
        sample_df = con.execute(
            f"SELECT * FROM read_parquet('{file_path}') LIMIT {sample_size}"
        ).fetchdf()
        render_df_table(sample_df, title=f"👀 Aperçu (Affiche {sample_size} premières lignes)")

    except Exception as e:
        console.print(f"[bold red]Erreur lors de la lecture du fichier :[/bold red] {e}")


def execute_custom_query(
    sql_query: str, title: str = "Résultat de la requête"
) -> None:
    """
    Exécute une requête SQL personnalisée en remplaçant les alias par vos fichiers Parquet.
    - 'meteo' est automatiquement remplacé par PARQUET_METEO
    - 'communes' est automatiquement remplacé par PARQUET_COMMUNES
    """
    try:
        con = duckdb.connect()

        # Remplacement automatique des alias par les vrais chemins Parquet
        formatted_query = sql_query.replace(
            "meteo", f"read_parquet('{PARQUET_METEO}')"
        ).replace("communes", f"read_parquet('{PARQUET_COMMUNES}')")

        df = con.execute(formatted_query).fetchdf()

        console.print(f"\n[bold yellow]🛠 Requête exécutee :[/bold yellow] [dim]{sql_query}[/dim]")
        render_df_table(df, title=title)

    except Exception as e:
        console.print(f"[bold red]Erreur lors de l'exécution SQL :[/bold red] {e}")


def render_df_table(df, title: str = "Résultat") -> None:
    """Transforme un DataFrame Pandas en un superbe tableau Rich dans la console."""
    if df.empty:
        console.print("[bold red]Aucun résultat retourné.[/bold red]")
        return

    table = Table(
        title=title,
        show_header=True,
        header_style="bold blue",
        row_styles=["none", "dim"],
    )

    for col in df.columns:
        table.add_column(str(col))

    for _, row in df.iterrows():
        # Conversion explicite en chaîne pour éviter les problèmes d'affichage Rich
        table.add_row(*[str(val) if val is not None else "" for val in row])

    console.print(table)


# ==============================================================================
# SCRIPT D'EXÉCUTION & EXEMPLES DE REQUÊTES SPECIFIQUES
# ==============================================================================
if __name__ == "__main__":

    # 1. Inspection rapide du fichier Météo
    console.print("\n[bold reverse blue]  1. RÉSUMÉ DU FICHIER MÉTÉO  [/bold reverse blue]")
    display_parquet_summary(PARQUET_METEO, table_alias="meteo", sample_size=5)

    # 2. Requête spécifique 1 : Lister les stations météo uniques les plus hautes
    console.print("\n[bold reverse blue]  2. REQUÊTES SPÉCIFIQUES  [/bold reverse blue]")

    query_1 = """
        SELECT DISTINCT NUM_POSTE, NOM_USUEL, LAT, LON, ALTI
        FROM meteo
        ORDER BY ALTI DESC
        LIMIT 5
    """
    execute_custom_query(query_1, title="🏔 Top 5 des stations les plus hautes")

    # 3. Requête spécifique 2 : Filtrer sur des dates précises
    query_2 = """
        SELECT NUM_POSTE, DATE, TMEAN, TMIN, TMAX
        FROM meteo
        WHERE DATE BETWEEN '2023-01-01' AND '2023-01-05'
        LIMIT 10
    """
    execute_custom_query(query_2, title="📅 Relevés météo début janvier 2023")

    # 4. Requête spécifique 3 : Croisement fictif (JOIN) entre Communes et Météo
    query_3 = """
        SELECT 
            c.nom AS commune,
            c.code_departement,
            m.NUM_POSTE,
            m.DATE,
            m.TMEAN
        FROM communes c
        CROSS JOIN meteo m
        WHERE c.code_departement = '75'
          AND m.DATE = '2023-01-15'
        LIMIT 5
    """
