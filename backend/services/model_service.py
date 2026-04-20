from backend.config import MODEL_VARIANT

_model = None


def _load_model():
    from ultralytics import YOLO
    return YOLO(MODEL_VARIANT)


def get_model():
    global _model
    if _model is None:
        _model = _load_model()
    return _model


def is_model_loaded() -> bool:
    return _model is not None
