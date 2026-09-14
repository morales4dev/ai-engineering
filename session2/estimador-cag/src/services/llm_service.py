from typing import Any

import litellm

from src.config import settings
from src.context.examples import ESTIMATION_EXAMPLES


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


def estimate_meeting(transcription: str) -> str:
	"""Generate a software estimation from a meeting transcription."""
	if not transcription.strip():
		raise ValueError("La transcripcion de la reunion no puede estar vacia")

	if settings.llm_provider.strip().lower() != "anthropic":
		raise NotImplementedError(
			f"Proveedor no soportado: {settings.llm_provider}. Solo se ha implementado Anthropic."
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
		model=settings.llm_model,
		api_key=settings.anthropic_api_key,
		messages=messages,
		temperature=0.2,
		max_tokens=2000,
	)
	content = response.choices[0].message.content
	if not content:
		raise RuntimeError("El modelo devolvio una respuesta vacia")

	return content
