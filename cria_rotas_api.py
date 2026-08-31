"""Script para modularizar servidor.py em routers temáticos em src/api/rotas/."""
from pathlib import Path

RAIZ = Path("src/api/rotas")
RAIZ.mkdir(parents=True, exist_ok=True)

(RAIZ / "__init__.py").write_text("""\"\"\"Pacote de rotas da API.\"\"\"
from . import executivo, politicos, entes, legislativo, controle
""", encoding="utf-8")

print("Estrutura de rotas inicializada!")
