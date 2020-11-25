import sys

import jinja2


def main():
    with open('Dockerfile.j2') as f:
        template = jinja2.Template(f.read())

    image = sys.argv[1]
    config = {
        'archlinux-webkit': {'webengine': False, 'unstable': False},
        'archlinux-webengine': {'webengine': True, 'unstable': False},
        'archlinux-webengine-unstable': {'webengine': True, 'unstable': True},
    }[image]

    with open('Dockerfile', 'w') as f:
        f.write(template.render(**config))
        f.write('\n')


if __name__ == '__main__':
    main()
