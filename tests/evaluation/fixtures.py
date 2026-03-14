# SPDX-License-Identifier: GPL-3.0-or-later

"""Test fixtures for ai-explain evaluation.

Each fixture represents a realistic user interaction:
  selected_text  — the text the user highlighted
  context        — the surrounding paragraph (what _JS_GET_CONTEXT returns)
  page_text      — the full page content (truncated, what dump_async returns)
"""

FIXTURES = [
    {
        "name": "coroutine",
        "selected_text": "coroutine",
        "context": (
            "Python supports coroutines with async and await syntax. "
            "Coroutines are computer program components that allow execution "
            "to be suspended and resumed, generalizing subroutines for "
            "cooperative multitasking."
        ),
        "page_text": (
            "Python is a high-level, general-purpose programming language. "
            "It supports multiple programming paradigms, including structured, "
            "object-oriented and functional programming. "
            "Python's coroutines are defined using async def and can be awaited "
            "using the await keyword. They are used extensively in asyncio-based "
            "concurrent programming. A coroutine is a specialization of a generator "
            "that can both yield values and receive values sent to it."
        ),
    },
    {
        "name": "garbage_collection",
        "selected_text": "garbage-collected",
        "context": (
            "Python is dynamically typed and garbage-collected. "
            "It supports multiple programming paradigms, including structured, "
            "object-oriented and functional programming."
        ),
        "page_text": (
            "Python is a high-level, general-purpose programming language. "
            "Python is dynamically typed and garbage-collected. "
            "Python uses reference counting to track object lifetimes, "
            "supplemented by a cyclic garbage collector for detecting and "
            "collecting reference cycles. Memory management in Python is "
            "handled automatically, freeing developers from manual allocation."
        ),
    },
    {
        "name": "global_interpreter_lock",
        "selected_text": "Global Interpreter Lock",
        "context": (
            "The Global Interpreter Lock (GIL) is a mechanism used in CPython "
            "to synchronize thread execution, allowing only one thread to execute "
            "Python bytecode at a time. This simplifies memory management but "
            "limits parallelism in CPU-bound multi-threaded programs."
        ),
        "page_text": (
            "CPython, the reference implementation of Python, uses a Global "
            "Interpreter Lock (GIL). The GIL prevents multiple native threads "
            "from executing Python bytecodes at once. This lock is necessary "
            "because CPython's memory management is not thread-safe. "
            "The GIL is controversial because it limits parallelism in "
            "CPU-bound multi-threaded programs. Alternative Python implementations "
            "like Jython and IronPython do not have a GIL."
        ),
    },
    {
        "name": "list_comprehension",
        "selected_text": "list comprehension",
        "context": (
            "Python supports list comprehensions, which provide a concise way "
            "to create lists based on existing lists or other iterables. "
            "A list comprehension consists of brackets containing an expression "
            "followed by a for clause, then zero or more for or if clauses."
        ),
        "page_text": (
            "Python has a number of compound expressions. A list comprehension "
            "has the form [expr for var in iterable if condition]. "
            "It is equivalent to a for loop that appends to a list but is more "
            "concise and often faster. "
            "For example: squares = [x**2 for x in range(10)] creates a list "
            "of squares. Generator expressions use parentheses instead of brackets "
            "and produce values lazily."
        ),
    },
    {
        "name": "duck_typing",
        "selected_text": "duck typing",
        "context": (
            "Python uses duck typing, meaning that the type or the class of an "
            "object is less important than the methods it defines. "
            "Using duck typing, any object that provides the expected interface "
            "can be used in place of another, regardless of its actual class."
        ),
        "page_text": (
            "Python is a dynamically-typed language that relies on duck typing. "
            "The name comes from the phrase: if it walks like a duck and quacks "
            "like a duck, then it must be a duck. In Python you do not declare "
            "variable types; the interpreter infers them at runtime. "
            "This makes Python code more flexible and reusable, at the cost of "
            "less static type safety compared to statically-typed languages."
        ),
    },
    {
        "name": "significant_indentation",
        "selected_text": "significant indentation",
        "context": (
            "Python's design philosophy emphasizes code readability with the use "
            "of significant indentation. Unlike many other languages that use "
            "braces or keywords to delimit blocks, Python uses indentation to "
            "define the structure and extent of code blocks."
        ),
        "page_text": (
            "Python is a high-level programming language whose design philosophy "
            "emphasizes code readability with significant indentation. "
            "Python requires consistent indentation to define block structure; "
            "mixing tabs and spaces is an error. This enforced style was a "
            "deliberate design decision by Guido van Rossum to make Python code "
            "visually uniform and easier to read across different codebases."
        ),
    },
]
