from unittest.mock import patch, MagicMock


def test_get_model_returns_instance():
    from backend.services.model_service import get_model
    with patch("backend.services.model_service._load_model") as mock_load:
        mock_load.return_value = MagicMock(name="YOLO")
        import backend.services.model_service as ms
        ms._model = None  # reset singleton
        model = get_model()
        assert model is not None


def test_get_model_singleton_loads_once():
    import backend.services.model_service as ms
    with patch("backend.services.model_service._load_model") as mock_load:
        mock_load.return_value = MagicMock(name="YOLO")
        ms._model = None
        m1 = get_model_fresh(ms)
        m2 = ms.get_model()
        assert m1 is m2
        mock_load.assert_called_once()


def test_get_model_returns_same_object_on_repeated_calls():
    import backend.services.model_service as ms
    sentinel = MagicMock(name="singleton-yolo")
    ms._model = sentinel
    assert ms.get_model() is sentinel
    assert ms.get_model() is sentinel


def test_model_loaded_flag_false_before_load():
    import backend.services.model_service as ms
    ms._model = None
    assert ms.is_model_loaded() is False


def test_model_loaded_flag_true_after_load():
    import backend.services.model_service as ms
    ms._model = MagicMock()
    assert ms.is_model_loaded() is True


# ── helpers ───────────────────────────────────────────────────────────────

def get_model_fresh(ms):
    ms._model = None
    return ms.get_model()
