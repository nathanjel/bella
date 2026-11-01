# clause: C-3-23
# spec: section 3
# status: P2+
# expect: ForwardRef
# source: decision S-1 (2026-11-01, docs/staging.md): evaluating the text of a ForwardRef stays [P2+]
"""ForwardRef.evaluate of an expression compiles the reference's text, which needs a compiler at
runtime; evaluating a plain name does not. Phase 1 evaluates the name and refuses the
expression with the milestone's name (spec section 3)."""
import annotationlib

print(annotationlib.ForwardRef("int").evaluate())
print(annotationlib.ForwardRef("list[int]").evaluate())
