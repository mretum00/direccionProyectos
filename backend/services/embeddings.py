"""
Embeddings: convertir texto en vectores numéricos.

- _obtener_modelo: carga el modelo de embeddings una sola vez y lo reutiliza.
- embedding_normalizado: pasa un texto a un vector de longitud 1, para poder
  compararlo con los vectores de la BD mediante similitud coseno.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings

# Modelo de embeddings ya cargado (se rellena la primera vez que se usa).
_modelo_embeddings = None


def _obtener_modelo():
    """Devuelve el modelo de embeddings, cargándolo solo la primera vez.

    Cargar el modelo tarda varios segundos, por eso se guarda en una variable
    global y las siguientes llamadas reutilizan el mismo.
    """
    global _modelo_embeddings

    if _modelo_embeddings is None:
        _modelo_embeddings = SentenceTransformer(settings.embedding_model)

    return _modelo_embeddings


def embedding_normalizado(texto: str) -> np.ndarray:
    """Convierte un texto en un vector de longitud 1.

    Los vectores de la BD también están normalizados (el generador usa
    normalize_embeddings=True), así que el producto escalar entre ambos es
    directamente la similitud coseno (de -1 a 1).
    """
    vector = _obtener_modelo().encode(texto, convert_to_numpy=True, show_progress_bar=False)
    vector = vector.astype(np.float32)
    # Dividir entre su longitud; el "or 1.0" evita dividir entre 0.
    return vector / (np.linalg.norm(vector) or 1.0)
