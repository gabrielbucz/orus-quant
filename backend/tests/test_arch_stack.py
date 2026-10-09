"""Stack real vs documentado — arquitetura.md §4 / spec.md §1.

Contrato: indicadores e backtest são Python puro. `pandas`/`numpy`/`ta`/
`scipy`/`statsmodels`/`vectorbt`/`backtrader` são PLANEJADOS (requisitos
comentados), não instalados nem importados. Se este teste quebrar porque uma
dessas libs passou a ser usada, mova-a para ativa no requirements.txt e para
"Implementado" nos docs junto — nunca só num dos lados.
"""

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
FUTURE_LIBS = ["pandas", "numpy", "ta", "scipy", "statsmodels", "vectorbt", "backtrader"]

_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z0-9_]+)", re.MULTILINE)


def _active_requirements() -> list[str]:
    lines = (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def _planned_requirements_raw() -> str:
    return (BACKEND / "requirements.txt").read_text(encoding="utf-8")


def test_requirements_nao_instalam_libs_futuras():
    active = _active_requirements()
    for lib in FUTURE_LIBS:
        assert not any(
            a.split(">")[0].split("=")[0].split("<")[0].strip() == lib for a in active
        ), f"'{lib}' ativo no requirements.txt mas documentado como planejado (arquitetura.md §4.2)"


def test_requirements_mantem_planejado_documentado():
    commented = [
        ln for ln in _planned_requirements_raw().splitlines() if ln.strip().startswith("#")
    ]
    for lib in FUTURE_LIBS:
        assert any(re.search(rf"\b{re.escape(lib)}\b", ln) for ln in commented), (
            f"'{lib}' sumiu até dos comentários — mantenha na seção Planejado "
            f"para futuros devs/agentes saberem da intenção"
        )


def test_codigo_nao_importa_libs_futuras():
    offenders: list[str] = []
    for py in list((BACKEND / "indicators").glob("*.py")) + list(
        (BACKEND / "backtest").glob("*.py")
    ) + list((BACKEND / "data").glob("*.py")) + list(
        (BACKEND / "strategy").glob("*.py")
    ):
        src = py.read_text(encoding="utf-8")
        for match in _IMPORT_RE.finditer(src):
            if match.group(1) in FUTURE_LIBS:
                offenders.append(f"{py.name}: {match.group(0).strip()}")
    assert not offenders, (
        "Import de lib planejada encontrado — atualize requirements.txt e "
        f"docs para Implementado junto: {offenders}"
    )


def test_import_runtime_nao_puxa_libs_futuras():
    import backtest.engine  # noqa: F401
    import indicators.core  # noqa: F401
    import indicators.engine  # noqa: F401

    loaded = [lib for lib in FUTURE_LIBS if lib in sys.modules]
    assert not loaded, f"libs planejadas carregadas em runtime: {loaded}"
