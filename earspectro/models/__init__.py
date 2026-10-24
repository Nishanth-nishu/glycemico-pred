from .classical import CLASSICAL_MODELS, build_classical
from .nets import SpectraNet

MODELS = ["mean", *CLASSICAL_MODELS, "ffnn", "cnn1d"]


def build_model(name: str, n_jobs: int = 4, seed: int = 0, **kw):
    if name == "ffnn":
        return SpectraNet(arch="ffnn", random_state=seed, **kw)
    if name == "cnn1d":
        return SpectraNet(arch="cnn1d", random_state=seed, **kw)
    return build_classical(name, n_jobs=n_jobs, seed=seed)


__all__ = ["MODELS", "build_model", "SpectraNet"]
