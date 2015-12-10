
import sys
import string

def filter_hints(words):

    alphabet = set("asdflkjqwerpoiu")
    hints = set()

    for word in words:

        # hints should be lowercase
        word = word.lower()

        # hints should be alphabetic
        if not set(word) <= alphabet:
            continue

        # hints shouldn't be longer than 5 characters
        if len(word) > 5:
            continue

        # hints should not be prefixes of other hints. we prefer the
        # longer ones.
        for i in range(len(word)):
            hints.discard(word[:i+1])

        hints.add(word)

    yield from hints

def main():
    inlines = (line.rstrip() for line in sys.stdin)
    outlines = ("{}\n".format(hint) for hint in filter_hints(inlines))
    sys.stdout.writelines(outlines)

if __name__ == "__main__":
    main()

