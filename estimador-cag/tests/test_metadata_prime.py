from prompts.loader import render_metadata_extraction_prompt
from sessions import ProjectMetadata


def test_extractor_prompt_renders_without_an_estimate() -> None:
    _, user = render_metadata_extraction_prompt(
        transcript="Team of 3. Nimbus CRM on React.",
        result=None,
        previous=ProjectMetadata(),
    )
    assert "no estimation yet" in user
    assert "Team of 3" in user
