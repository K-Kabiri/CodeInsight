from .halstead import HalsteadEngine
from .loc import LOCEngine
from .cyclomatic import CyclomaticComplexityEngine
from .cognitive import CognitiveComplexityEngine


ENGINE_REGISTRY = {
    "LOC": LOCEngine,
    "CYCLOMATIC": CyclomaticComplexityEngine,
    "COGNITIVE": CognitiveComplexityEngine,
    "Halstead": HalsteadEngine,
}


def get_engine(metric_name: str):
    engine_class = ENGINE_REGISTRY.get(metric_name)

    if engine_class is None:
        raise ValueError(
            f"No engine registered for metric: {metric_name}"
        )

    return engine_class()