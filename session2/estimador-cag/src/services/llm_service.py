from typing import Any
from dataclasses import dataclass
import litellm
from ..config import get_settings
from ..context.examples import ESTIMATION_EXAMPLES
from ..schemas.estimation import ExampleFormat, PreprocessingMode


settings = get_settings()


DEFAULT_MAX_TOKENS = 4000
EXTRACTION_MAX_TOKENS = 1500

@dataclass
class GenerationOptions:
    """Per-request knobs that drive prompt construction and the LLM call."""

    preprocessing: PreprocessingMode = "none"
    example_format: ExampleFormat = "markdown"
    num_examples: int = 3
    use_examples: bool = True
    model: str | None = None
    max_tokens: int = DEFAULT_MAX_TOKENS
    thinking_budget: int | None = None


def build_system_prompt(examples: list[dict[str, str]] = ESTIMATION_EXAMPLES) -> str:
	"""Build the system instructions and inject historical estimations."""
	examples_text = "\n\n".join(
		f"### Ejemplo {index}\n"
		f"Resumen de la reunion:\n{example['meeting_summary']}\n\n"
		f"Estimacion generada:\n{example['estimation']}"
		for index, example in enumerate(examples, start=1)
	)

	return f"""Eres un estimador de software experto.

Genera una estimacion profesional basandote en los ejemplos historicos incluidos
y en la transcripcion de la nueva reunion. Identifica el alcance, desglosa el
trabajo en tareas concretas, estima las horas y los costes, e indica el total,
el equipo recomendado y la duracion aproximada. Si la transcripcion no aporta
informacion suficiente, indica claramente las incertidumbres y los supuestos.
No inventes requisitos que no aparezcan en la transcripcion sin marcarlos como
supuestos. Responde en espanol y conserva un formato claro en Markdown.

Estos son ejemplos de estimaciones previas que sirven como referencia de estilo
y nivel de detalle:

{examples_text}"""


def generate_estimation(
    transcription: str,
    opts: GenerationOptions | None = None,
) -> dict:
	"""Generate a software estimation from a meeting transcription."""
	if not transcription.strip():
		raise ValueError("La transcripcion de la reunion no puede estar vacia")

	if settings.LLM_PROVIDER.strip().lower() != "anthropic":
		raise NotImplementedError(
			f"Proveedor no soportado: {settings.LLM_PROVIDER}. Solo se ha implementado Anthropic."
		)

	messages = [
		{"role": "system", "content": build_system_prompt()},
		{
			"role": "user",
			"content": (
				"Genera una estimacion para la siguiente transcripcion de reunion:\n\n"
				f"{transcription}"
			),
		},
	]

	response: Any = litellm.completion(
		model=settings.LLM_MODEL,
		api_key=settings.ANTHROPIC_API_KEY,
		messages=messages,
		temperature=0.2,
		max_tokens=2000,
	)
	content = response.choices[0].message.content
	if not content:
		raise RuntimeError("El modelo devolvio una respuesta vacia")

	return content
