def test_corpus_panel_submits_json_and_displays_failures(monkeypatch):
    import httpx
    from streamlit.testing.v1 import AppTest

    calls = []

    def get(url, **kwargs):
        body = {"total_chunks": 0, "hnsw_indexed": False, "collections": []}
        if url.endswith("/runs"):
            body = []
        return httpx.Response(200, request=httpx.Request("GET", url), json=body)

    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(422, request=httpx.Request("POST", url), text="invalid budget")

    monkeypatch.setattr("corpus_ui.httpx.get", get)
    monkeypatch.setattr("corpus_ui.httpx.post", post)
    app = AppTest.from_string(
        "from corpus_ui import render_corpus\nrender_corpus('http://test', 'key')"
    ).run()
    app.text_area[0].set_value('{"budget_id": "bad"}')
    app.button[0].click().run()
    assert not app.exception
    assert calls[0]["documents"] == [{"budget_id": "bad"}]
    assert "invalid budget" in app.error[0].value
