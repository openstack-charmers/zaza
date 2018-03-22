import argparse


def parser(args=None):
    parser = argparse.ArgumentParser(
        description='build tempest config from currently deployed model')
    parser.add_argument('blacklist',
                        help='Comma seperated list of'
                             'additional tests to ignore',
                        default='', nargs='?')
    return parser.parse_known_args(args)


def main():
    a, extra = parser()
    blacklist = list(filter(bool, a.blacklist.split(",")))
    print("Starting with blacklist of {}".format(blacklist))


if __name__ == '__main__':
    main()
