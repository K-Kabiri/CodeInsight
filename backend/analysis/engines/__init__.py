from .halstead import HalsteadEngine
from .loc import LOCEngine
from .cyclomatic import CyclomaticComplexityEngine
from .cognitive import CognitiveComplexityEngine
from .cbo import CBOEngine
from .lcom import LCOMEngine
from .dit import DITEngine
from .instability import InstabilityEngine
from .cyclic import CyclicDependenciesEngine
from .violations import RuleViolationsEngine
from .code_smells import CodeSmellsEngine
from .duplication import DuplicationEngine


ENGINE_REGISTRY = {
    "LOC": LOCEngine,
    "CYCLOMATIC": CyclomaticComplexityEngine,
    "COGNITIVE": CognitiveComplexityEngine,
    "Halstead": HalsteadEngine,
    "CBO": CBOEngine,
    "LCOM": LCOMEngine,
    "DIT": DITEngine,
    "INSTABILITY": InstabilityEngine,
    "CYCLIC": CyclicDependenciesEngine,
    "VIOLATIONS": RuleViolationsEngine,
    "CODE_SMELLS": CodeSmellsEngine,
    "DUPLICATION": DuplicationEngine,
}


def get_engine(metric_name: str):
    engine_class = ENGINE_REGISTRY.get(metric_name)

    if engine_class is None:
        raise ValueError(
            f"No engine registered for metric: {metric_name}"
        )

    return engine_class()