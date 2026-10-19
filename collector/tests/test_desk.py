from fastapi.testclient import TestClient

from app import main


def test_a_panel_gets_an_answer_by_its_name(store):
    main.app.state.store = store
    client = TestClient(main.app)

    answer = client.get("/api/desk/home").json()

    assert (answer["name"], answer["stale"], answer["screens"]) == ("home", False, [])
    assert answer["as_of"]
    assert client.get("/api/desk/test").status_code == 200
    assert client.get("/api/desk/kitchen").status_code == 422
