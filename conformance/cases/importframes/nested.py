from importframes.show import stack

stack("nested outer")
import importframes.nested_inner  # noqa: E402, F401
