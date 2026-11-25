import warnings

warnings.warn("its own line", UserWarning, stacklevel=1)
warnings.warn("the importer's line", UserWarning, stacklevel=2)
