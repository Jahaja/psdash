import locale
import argparse
import logging
import time
import threading
from logging import getLogger
from flask import Flask, render_template
from psdash.log import Logs
from psdash.net import NetIOCounters


logger = getLogger('psdash.run')


# Patch the built-in, but not working, filesizeformat filter for now.
# See https://github.com/mitsuhiko/jinja2/pull/59 for more info.
def filesizeformat(value, binary=False):
    '''Format the value like a 'human-readable' file size (i.e. 13 kB,
    4.1 MB, 102 Bytes, etc).  Per default decimal prefixes are used (Mega,
    Giga, etc.), if the second parameter is set to `True` the binary
    prefixes are used (Mebi, Gibi).
    '''
    bytes = float(value)
    base = binary and 1024 or 1000
    prefixes = [
        (binary and 'KiB' or 'kB'),
        (binary and 'MiB' or 'MB'),
        (binary and 'GiB' or 'GB'),
        (binary and 'TiB' or 'TB'),
        (binary and 'PiB' or 'PB'),
        (binary and 'EiB' or 'EB'),
        (binary and 'ZiB' or 'ZB'),
        (binary and 'YiB' or 'YB')
    ]
    if bytes == 1:
        return '1 Byte'
    elif bytes < base:
        return '%d Bytes' % bytes
    else:
        for i, prefix in enumerate(prefixes):
            unit = base ** (i + 2)
            if bytes < unit:
                return '%.1f %s' % ((base * bytes / unit), prefix)
        return '%.1f %s' % ((base * bytes / unit), prefix)


def load_allowed_remote_addresses(app):
    key = 'PSDASH_ALLOWED_REMOTE_ADDRESSES'
    addrs = app.config.get(key)
    if not addrs:
        return

    if isinstance(addrs, (str, unicode)):
        app.config[key] = [a.strip() for a in addrs.split(',')]


class PsDashContext(object):
    def __init__(self):
        self.logs = Logs()
        self.net_io_counters = NetIOCounters()


class PsDashApp(Flask):
    def __init__(self, *args, **kwargs):
        super(PsDashApp, self).__init__(*args, **kwargs)
        self.psdash = PsDashContext()


def create_app(config=None):
    app = PsDashApp(__name__)
    app.config.from_envvar('PSDASH_CONFIG', silent=True)

    if config and isinstance(config, dict):
        app.config.update(config)

    load_allowed_remote_addresses(app)

    # If the secret key is not read from the config just set it to something.
    if not app.secret_key:
        app.secret_key = 'whatisthissourcery'
    app.add_template_filter(filesizeformat)

    app_url_prefix = app.config.get('PSDASH_URL_PREFIX')
    if app_url_prefix:
        app_url_prefix = '/' + app_url_prefix.strip('/')

    from psdash.web import webapp
    webapp.url_prefix = app_url_prefix
    app.register_blueprint(webapp)

    return app


def parse_args():
    parser = argparse.ArgumentParser(
        description='psdash %s - system information web dashboard' % '0.3.0'
    )
    parser.add_argument(
        '-l', '--log',
        action='append',
        dest='logs',
        default=[],
        metavar='path',
        help='log files to make available for psdash. Patterns (e.g. /var/log/**/*.log) are supported. '
             'This option can be used multiple times.'
    )
    parser.add_argument(
        '-b', '--bind',
        action='store',
        dest='bind_host',
        default='0.0.0.0',
        metavar='host',
        help='host to bind to. Defaults to 0.0.0.0 (all interfaces).'
    )
    parser.add_argument(
        '-p', '--port',
        action='store',
        type=int,
        dest='port',
        default=5000,
        metavar='port',
        help='port to listen on. Defaults to 5000.'
    )
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        dest='debug',
        help='enables debug mode.'
    )

    return parser.parse_args()


def start_background_worker(app, args, sleep_time=3):
    def work():
        update_logs_interval = 60
        i = update_logs_interval
        while True:
            app.psdash.net_io_counters.update()

            # update the list of available logs every minute
            if update_logs_interval <= 0:
                app.psdash.logs.add_patterns(args.logs)
                i = update_logs_interval
            i -= sleep_time

            time.sleep(sleep_time)

    t = threading.Thread(target=work)
    t.daemon = True
    t.start()


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s | %(name)s | %(message)s'
    )

    logging.getLogger('werkzeug').setLevel(logging.WARNING)


def enable_verbose_logging():
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('psdash.web').setLevel(logging.DEBUG)


def main():
    setup_logging()

    logger.info('Starting psdash v0.3.0')

    # This set locale to the user default (usually controlled by the LANG env var)
    locale.setlocale(locale.LC_ALL, '')

    args = parse_args()
    if args.debug:
        enable_verbose_logging()

    app = create_app()
    app.psdash.logs.add_patterns(args.logs)
    start_background_worker(app, args)

    logger.info('Listening on %s:%s', args.bind_host, args.port)

    app.run(
        host=args.bind_host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )


if __name__ == '__main__':
    main()