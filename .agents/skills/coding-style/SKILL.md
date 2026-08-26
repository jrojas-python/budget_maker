---
name: coding-style
description: Genera código Python que siga exactamente las convenciones de este proyecto (Anita 2.0 Orchestrator). Aplica las reglas de nombrado, type hints, factory de nodos LangGraph, logging, error handling, docstrings en español e imports antes de escribir cualquier línea de código. Úsalo cuando necesites crear un nuevo nodo, helper, schema, servicio o cualquier pieza de código Python en este proyecto.
tags: [python, coding-style, langgraph, conventions, anita, backend]
---

# Coding Style — Anita 2.0 Orchestrator

## Tarea

$ARGUMENTS

---

> Lee **todas** las reglas a continuación antes de escribir cualquier código.
> Al terminar la implementación, ejecuta mentalmente el **Checklist final** antes de entregar.

---

## 1. Nombrado

| Caso | Patrón | Ejemplo real del proyecto |
|---|---|---|
| Variables y parámetros | `snake_case` | `user_input`, `blocked_category`, `onboarding_data` |
| Constantes públicas de módulo | `UPPER_CASE` | `FAITHFULNESS_THRESHOLD = 0.5`, `MIN_CONTEXT_CHARS = 30` |
| Constantes privadas de módulo | `_UPPER_CASE` | `_SCHEMAS_DIR`, `_COMPILED_PATTERNS`, `_LLM_CONFIDENCE_THRESHOLD` |
| Funciones / helpers privados | `_nombre` | `_normalize`, `_detect_blocked`, `_validate_id_number` |
| Factory de nodos LangGraph | `make_*_node` | `make_blocked_list_node`, `make_grounding_node` |
| Detección booleana pública | `is_*` | `is_advisor_request`, `is_critical_intent` |
| Detección booleana privada | `_is_*` | `_is_affirmative`, `_is_negative`, `_is_closing_phrase` |
| Loaders con caché | `_load_*` | `_load_blocked_patterns`, `_load_messages`, `_load_prompt` |
| Campos de estado / dominio | Español + inglés técnico | `onboarding_step`, `advisor_transfer`, `retrieved_context` |
| Enumerados | `CamelCase(str, Enum)` | `OnboardingStep`, `AdvisorState` |
| Modelos Pydantic | `CamelCase` + campos en español | `AnitaChatResponse`, campo `tipo_respuesta` |

---

## 2. Type hints

Usar siempre **sintaxis Python 3.10+**. Nunca `Optional`, `Tuple`, `List`, `Dict` de `typing`.

```python
# CORRECTO
def _detect(text: str) -> tuple[bool, str | None]: ...
def _load_data() -> list[tuple[str, re.Pattern]]: ...
def get(self, sid: str) -> dict[str, Any]: ...

# INCORRECTO — no usar
from typing import Optional, Tuple, List, Dict
def _detect(text: str) -> Tuple[bool, Optional[str]]: ...
```

- `TypedDict` para el estado del grafo (`AgentState`) — nunca Pydantic para estado
- `Pydantic BaseModel` para schemas de respuesta LLM con campos en español
- `str, Enum` para valores de paso / estado
- `Callable[[AgentState], AgentState]` como tipo de retorno en factories

---

## 3. Factory de nodos LangGraph

**Patrón obligatorio**: la función pública es una factory que devuelve un closure. Los recursos se cargan una sola vez en el cuerpo de la factory, no dentro del nodo.

```python
def make_mi_nodo(
    client: AzureOpenAI,
    deployment: str,
    config: dict | None = None,
) -> Callable[[AgentState], AgentState]:
    """
    Retorna el nodo `mi_nodo` para el grafo LangGraph.

    Campos de estado utilizados:
      - question       : pregunta actual del usuario
      - onboarding_data: contexto acumulado de la conversación
      - campo_salida   : resultado que este nodo escribe
    """
    # Precargar recursos una sola vez (aquí, no dentro del nodo)
    patrones = _load_patrones()

    def mi_nodo(state: AgentState) -> AgentState:
        question = state.get("question") or ""

        # Early return si no hay nada que procesar
        if not question.strip():
            return state

        # ... lógica del nodo ...

        return {**state, "campo_salida": resultado}

    return mi_nodo
```

Reglas del closure interno:
- Siempre recibe `state: AgentState` y retorna `AgentState`
- Mutación de estado **siempre** vía dict unpacking: `{**state, "key": value}`
- Early returns para reducir anidamiento — nunca anidar más de 3 niveles
- Returns de tupla para múltiples valores: `tuple[bool, str]`
- **Nunca lambdas** — siempre funciones con nombre

---

## 4. Logging

```python
# Al inicio de cada módulo — siempre esta línea
logger = logging.getLogger(__name__)

# Formato de mensajes (prefijo [nombre_nodo] para trazabilidad)
logger.info("[mi_nodo] procesando pregunta | question=%r", question[:80])
logger.warning("[mi_nodo] patrón bloqueado | category=%s input=%r", category, text[:60])
logger.error("[mi_nodo] JSON no encontrado en %s", path)
logger.warning("[mi_nodo] error en LLM | exc=%s", exc, exc_info=True)
```

Reglas:
- Usar **`%s` siempre** en los argumentos del logger — nunca f-strings dentro de la llamada
- `exc_info=True` en todos los `except` que loggeen errores o warnings de excepción
- Incluir el nombre del nodo como prefijo `[nombre_nodo]`
- Incluir campos clave del contexto: `category=`, `input=`, `session_id=`, `score=`

---

## 5. Manejo de errores y loaders

```python
_CONFIG_DIR = Path(__file__).parent.parent.parent / "carpeta_config"

@lru_cache(maxsize=1)
def _load_config() -> dict:
    """Carga la configuración del nodo. Fail-open: retorna {} si no existe."""
    path = _CONFIG_DIR / "config.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("config.json no encontrado en %s", path)
        return {}
    except json.JSONDecodeError as exc:
        logger.error("JSON inválido en %s: %s", path, exc)
        return {}
```

Reglas:
- `@lru_cache(maxsize=1)` **obligatorio** en toda función que lea disco
- `Path(__file__).parent...` para construir rutas relativas al archivo actual
- `encoding="utf-8"` **siempre** explícito en `read_text()`
- **Fail-open**: retornar default vacío seguro (`{}`, `[]`, `""`) — no propagar excepciones en loaders
- `except Exception as exc` solo como último recurso después de tipos específicos

---

## 6. Imports

```python
from __future__ import annotations          # SIEMPRE primera línea del archivo

import json                                 # stdlib
import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Callable                 # solo lo que se usa; nunca Optional/Tuple/List/Dict

from openai import AzureOpenAI             # terceros

from ..chatbot_state import AgentState     # proyecto (imports relativos)
from ...response_schemas.anita_response import AnitaChatResponse
```

Orden obligatorio:
1. `from __future__ import annotations`
2. stdlib (con sub-secciones por módulo si son muchos)
3. terceros (fastapi, openai, pydantic, langgraph, etc.)
4. proyecto (imports relativos `..` o `...`)

Sin aliases salvo colisión real de nombres. Sin imports no utilizados.

---

## 7. Docstrings y comentarios

```python
def _normalize(text: str) -> str:
    """Minúsculas y sin tildes para comparaciones robustas."""
    ...

def make_injection_guard_node(
    client: AzureOpenAI,
    deployment: str,
) -> Callable[[AgentState], AgentState]:
    """
    Retorna el nodo `injection_guard` que detecta intentos de inyección.

    Campos de estado utilizados:
      - question    : texto de entrada del usuario
      - is_blocked  : se establece True si se detecta inyección
      - answer      : respuesta de bloqueo pre-formateada
    """
    ...
```

Secciones con separadores visuales:

```python
# ──────────────────────────────────────────────────────────────────────────────
# Carga de JSONs — una sola vez gracias a lru_cache
# ──────────────────────────────────────────────────────────────────────────────

#====>Etapa 1: Validación heurística inicial
#---->Capa 1: Regex de patrones bloqueados
```

Reglas:
- Docstrings en **español**
- Una línea para helpers simples
- Multi-línea para factories: incluir sección "Campos de estado utilizados"
- NO documentar cada función; priorizar factories, helpers complejos y funciones públicas
- Comentarios en español; inglés solo para términos técnicos sin traducción

---

## 8. Constantes y configuración

```python
# Constantes de umbral
FAITHFULNESS_THRESHOLD = 0.5
_LLM_CONFIDENCE_THRESHOLD = 0.85

# Rutas de recursos
_SCHEMAS_DIR    = Path(__file__).parent.parent.parent / "question_schemas"
_ONBOARDING_DIR = Path(__file__).parent.parent.parent / "onboarding_schemas"
_PROMPTS_DIR    = Path(__file__).parent.parent.parent / "prompt"

# Conjuntos inmutables
_ADVISOR_PENDING_CATEGORIES: frozenset[str] = frozenset({"fraud_prize", "fraud_account"})

# Variables de entorno
from settings.config import _config
SEARCH_ENDPOINT = _config("SEARCH_ENDPOINT")
EMBEDDING_DEPLOYMENT = _config("EMBEDDING_DEPLOYMENT")
```

---

## 9. Patrones de retorno

```python
# Retorno de estado del nodo
return {**state, "is_blocked": True, "blocked_category": category, "answer": respuesta}

# Retorno temprano (sin cambios)
return state

# Retorno de tupla desde helper
return False, f"El {id_type} debe tener entre {min_len} y {max_len} caracteres."

# Retorno condicional compacto
return "end" if not state.get("question", "").strip() else "advisor_route"
```

---

## Checklist final

Antes de entregar el código, verificar **cada punto**:

- [ ] Nombres: `make_*_node` para factories, `is_*` / `_is_*` para booleanas, `_load_*` para loaders, `UPPER_CASE` para constantes
- [ ] Type hints Python 3.10+: `str | None`, `tuple[bool, str]` — sin `Optional`, `Tuple`, `List`, `Dict`
- [ ] Nodo implementado como closure dentro de factory con precargas fuera del closure
- [ ] Estado retornado con `{**state, "key": value}` — nunca mutación directa
- [ ] `logger = logging.getLogger(__name__)` al inicio del módulo
- [ ] Logs usan `%s`, nunca f-strings en argumentos del logger
- [ ] Loaders con `@lru_cache(maxsize=1)`, `Path(__file__).parent...`, `encoding="utf-8"`, fail-open
- [ ] `from __future__ import annotations` es la primera línea del archivo
- [ ] Imports ordenados: stdlib → terceros → proyecto
- [ ] Docstrings y comentarios en español
- [ ] Early returns para reducir anidamiento; sin lambdas
