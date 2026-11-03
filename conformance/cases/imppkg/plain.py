"""A plain submodule (C-8-10)."""
X = 1
print("imppkg.plain: body runs;", __name__, __package__, __spec__.parent, __spec__.submodule_search_locations)
