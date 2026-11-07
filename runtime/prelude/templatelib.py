"""The t-string types, in Python (Objects/templateobject.c, Objects/interpolationobject.c): Template, Interpolation and the template
iterator, which string.templatelib takes from type(t""); the intrinsics `template` and `interpolation` are what BUILD_TEMPLATE and
BUILD_INTERPOLATION make. The three are built-in types of no module's namespace: __hidden_classes__ presents them as C types."""

__all__: list[str] = []
__intrinsics__ = ["template", "interpolation"]
__hidden_classes__ = ["Template", "Interpolation", "TemplateIter"]

try:
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
except NameError:
    _bella_new_instance = object.__new__

    def _tp_name(obj: object) -> str:
        t = type(obj)
        return t.__name__ if t.__module__ in ("builtins", "__main__") else t.__module__ + "." + t.__name__


def _new_receiver(args: tuple[object, ...], owner: type, shown: str) -> None:   # tp_new_wrapper's checks
    if not args:
        raise TypeError(shown + ".__new__(): not enough arguments")
    cls = args[0]
    if not issubclass(type(cls), type):
        raise TypeError(shown + ".__new__(X): X is not a type object (" + _tp_name(cls) + ")")
    if not issubclass(cls, owner):  # type: ignore[arg-type]
        raise TypeError(shown + ".__new__(" + cls.__name__ + "): " + cls.__name__ + " is not a subtype of " + shown)  # type: ignore[attr-defined]


class Interpolation:
    """Interpolation object"""

    __module__ = "string.templatelib"
    __slots__ = ("_value", "_expression", "_conversion", "_format_spec")
    __match_args__ = ("value", "expression", "conversion", "format_spec")

    def __new__(*args: object, **kwds: object) -> Interpolation:   # noqa: N805  # interpolation_new (Argument Clinic)
        _new_receiver(args, Interpolation, "string.templatelib.Interpolation")
        names = ("value", "expression", "conversion", "format_spec")
        given = args[1:]
        if len(given) + len(kwds) > 4:
            raise TypeError("Interpolation() takes at most 4 " + ("keyword " if not given else "") + "arguments (" + str(len(given) + len(kwds)) + " given)")
        values: list[object] = list(given)
        for name in names[len(given):]:
            if name in kwds:
                values.append(kwds.pop(name))
            else:
                values.append(_ABSENT)
        for key in kwds:
            if key in names:
                raise TypeError("argument for Interpolation() given by name ('" + key + "') and position (" + str(names.index(key) + 1) + ")")
            raise TypeError("Interpolation() got an unexpected keyword argument '" + key + "'")
        value, expression, conversion, format_spec = values
        if value is _ABSENT:
            raise TypeError("Interpolation() missing required argument 'value' (pos 1)")
        if expression is _ABSENT:
            expression = ""
        elif not isinstance(expression, str):
            raise TypeError("Interpolation() argument 'expression' must be str, not " + _tp_name(expression))
        if conversion is _ABSENT:
            conversion = None
        elif conversion is not None:             # _conversion_converter
            if not isinstance(conversion, str):
                raise TypeError("Interpolation() argument 'conversion' must be str, not " + _tp_name(conversion))
            if len(conversion) != 1 or conversion not in ("a", "r", "s"):
                raise ValueError("Interpolation() argument 'conversion' must be one of 's', 'a' or 'r'")
        if format_spec is _ABSENT:
            format_spec = ""
        elif not isinstance(format_spec, str):
            raise TypeError("Interpolation() argument 'format_spec' must be str, not " + _tp_name(format_spec))
        self: Interpolation = _bella_new_instance(args[0])
        self._value = value
        self._expression = expression
        self._conversion = conversion
        self._format_spec = format_spec
        return self

    @property
    def value(self) -> object:
        return self._value

    @property
    def expression(self) -> object:
        return self._expression

    @property
    def conversion(self) -> object:
        return self._conversion

    @property
    def format_spec(self) -> object:
        return self._format_spec

    def __repr__(self) -> str:                   # interpolation_repr: %s(%R, %R, %R, %R) with _PyType_Name
        return type(self).__name__ + "(" + repr(self._value) + ", " + repr(self._expression) + ", " + repr(self._conversion) + ", " + repr(self._format_spec) + ")"

    def __reduce__(self) -> object:
        """__reduce__() -> (cls, state)"""
        return (type(self), (self._value, self._expression, self._conversion, self._format_spec))


class _Absent:
    pass


_ABSENT = _Absent()


def _build(strings: tuple[str, ...], interpolations: tuple[Interpolation, ...]) -> Template:   # _PyTemplate_Build
    self: Template = _bella_new_instance(Template)
    self._strings = strings
    self._interpolations = interpolations
    return self


class Template:
    """Template object"""

    __module__ = "string.templatelib"
    __slots__ = ("_strings", "_interpolations")

    def __new__(*args: object, **kwds: object) -> Template:   # noqa: N805  # template_new
        _new_receiver(args, Template, "string.templatelib.Template")
        if kwds:
            raise TypeError("Template.__new__ only accepts *args arguments")
        for item in args[1:]:
            if not isinstance(item, str) and type(item) is not Interpolation:
                raise TypeError("Template.__new__ *args need to be of type 'str' or 'Interpolation', got " + _tp_name(item))
        strings: list[str] = []
        interpolations: list[Interpolation] = []
        last_was_str = False
        for item in args[1:]:
            if isinstance(item, str):
                if last_was_str:
                    strings[-1] = str.__add__(strings[-1], item)   # PyUnicode_Concat
                else:
                    strings.append(item)
                last_was_str = True
            else:
                if not last_was_str:
                    strings.append("")
                interpolations.append(item)  # type: ignore[arg-type]
                last_was_str = False
        if not last_was_str:
            strings.append("")
        return _build(tuple(strings), tuple(interpolations))

    @property
    def strings(self) -> object:
        return self._strings

    @property
    def interpolations(self) -> object:
        return self._interpolations

    @property
    def values(self) -> object:                  # template_values_get
        return tuple(i._value for i in self._interpolations)

    def __repr__(self) -> str:                   # template_repr
        return type(self).__name__ + "(strings=" + repr(self._strings) + ", interpolations=" + repr(self._interpolations) + ")"

    def __iter__(self) -> TemplateIter:        # template_iter
        it: TemplateIter = _bella_new_instance(TemplateIter)
        it._stringsiter = iter(self._strings)
        it._interpolationsiter = iter(self._interpolations)
        it._from_strings = True
        return it

    def __add__(self, other: object) -> Template:   # sq_concat: _PyTemplate_Concat
        if type(other) is not Template:
            raise TypeError('can only concatenate string.templatelib.Template (not "' + _tp_name(other) + '") to string.templatelib.Template')
        left, right = self._strings, other._strings
        strings = (*left[:-1], str.__add__(left[-1], right[0]), *right[1:])   # template_strings_concat
        return _build(strings, self._interpolations + other._interpolations)

    def __reduce__(self) -> object:             # template_reduce
        import string.templatelib

        return (string.templatelib._template_unpickle, (self._strings, self._interpolations))


class TemplateIter:
    """Template iterator object"""

    __module__ = "string.templatelib"
    __slots__ = ("_stringsiter", "_interpolationsiter", "_from_strings")

    def __iter__(self) -> TemplateIter:
        return self

    def __next__(self) -> object:                # templateiter_next: a string, then an interpolation; an empty string is skipped
        if self._from_strings:
            self._from_strings = False
            item = next(self._stringsiter)
            if len(item) == 0:
                item = next(self._interpolationsiter)
                self._from_strings = True
            return item
        self._from_strings = True
        return next(self._interpolationsiter)


template = Template
interpolation = Interpolation
