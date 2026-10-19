from app.panel_text import latin1


def test_text_is_kept_to_what_the_panel_fonts_hold():
    text = "Utrecht – Amsterdam ‘werk’… café"
    assert latin1(text) == "Utrecht - Amsterdam 'werk'... café"
    assert latin1("Samen V2 ❤️❤️") == "Samen V2"
    assert latin1("→ Zwolle") == "Zwolle"
