"""The staging prototype (Gate 0 task 5; docs/staging.md): a dry run that records the code
the standard library and the program generate at definition time, a replay model that runs a
program with that code and no exec, and the annotationlib shim's build-time tables."""
# the dry run's exit status when the tool itself failed, not the program it ran: the build then fails, where a program that ends
# the process only leaves nothing staged (review F17 #15)
TOOL_FAILED = 113
