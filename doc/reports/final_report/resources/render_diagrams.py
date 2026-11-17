"""Génère les PNG des diagrammes Mermaid du rapport final avec Chrome en mode headless.

Usage (depuis doc/reports/final_report) : python resources/render_diagrams.py
Chaque fichier resources/mermaid/<nom>.mmd devient resources/diagrams_final/<nom>.png.
Nécessite Chrome, Pillow et un accès à cdn.jsdelivr.net (mermaid.js).
"""

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

ICI = Path(__file__).resolve().parent
SOURCES = ICI / "mermaid"
SORTIE = ICI / "diagrams_final"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<style>body{margin:0;padding:30px;background:white;font-family:Arial}</style></head>
<body><div style="width:%s"><pre class="mermaid">%s</pre></div>
<script>mermaid.initialize({startOnLoad:true, theme:"default", fontFamily:"Arial",
  flowchart:{useMaxWidth:false, htmlLabels:true}, class:{useMaxWidth:false},
  er:{useMaxWidth:false}, sequence:{useMaxWidth:false}, gantt:{useMaxWidth:true, fontSize:15, sectionFontSize:15, barHeight:26, barGap:6, leftPadding:110}});</script>
</body></html>"""


def rogner(chemin: Path) -> None:
    """Retire le blanc autour du diagramme, en gardant une petite marge."""
    image = Image.open(chemin).convert("RGB")
    fond = Image.new("RGB", image.size, "white")
    boite = ImageChops.difference(image, fond).getbbox()
    if boite:
        marge = 20
        boite = (max(boite[0] - marge, 0), max(boite[1] - marge, 0),
                 min(boite[2] + marge, image.width), min(boite[3] + marge, image.height))
        image.crop(boite).save(chemin)


def main() -> None:
    SORTIE.mkdir(exist_ok=True)
    for source in sorted(SOURCES.glob("*.mmd")):
        texte = source.read_text(encoding="utf-8").replace("<", "&lt;").replace(">", "&gt;")
        with tempfile.TemporaryDirectory() as dossier:
            html = Path(dossier) / "page.html"
            largeur = "1150px" if texte.lstrip().startswith("gantt") else "auto"
            html.write_text(PAGE % (largeur, texte), encoding="utf-8")
            png = SORTIE / f"{source.stem}.png"
            subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                 "--force-device-scale-factor=2", "--window-size=2200,3200",
                 "--virtual-time-budget=8000", f"--screenshot={png}", html.as_uri()],
                check=True, capture_output=True,
            )
        rogner(png)
        print(f"{png.name} : {Image.open(png).size}")


if __name__ == "__main__":
    main()
