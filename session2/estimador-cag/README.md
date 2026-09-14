## Install

cd $WORKSPACE_HOME/ai-engineering/session2/estimador-cag
uv venv .venv --python 3.12.12
source .venv/bin/activate
uv pip install --python .venv/bin/python -r requirements.txt

## Test

curl -X POST http://localhost:8000/api/v1/estimate   -H "Content-Type: application/json"   -d '{
    "transcription": "En la reunión con el equipo de marketing, el cliente explicó que necesita una landing page con formulario de contacto, integración con su CRM actual (HubSpot), y una sección de blog con editor WYSIWYG. El plazo ideal sería tenerlo listo en 4 semanas. El diseño ya existe en Figma."
  }' -o salida.json

jq -r '.estimation' salida.json > estimacion-limpia.md
