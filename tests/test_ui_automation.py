from app.windows.action_router import WindowsActionRouter


def test_semantic_click_target_extracts_named_control():
    router = WindowsActionRouter.__new__(WindowsActionRouter)
    assert router._semantic_click_target("click the Promotions tab") == "Promotions tab"


def test_semantic_click_target_ignores_coordinates():
    router = WindowsActionRouter.__new__(WindowsActionRouter)
    assert router._semantic_click_target("click at 640, 480") is None
