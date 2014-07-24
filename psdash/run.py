import locale
import argparse
import logging
import time
import threading
from logging import getLogger
from flask import Flask, render_template
from psdash.log import Logs
from psdash.net import NetIOCounters
from psdash.web import filesizeformat


logger = getLogger('psdash.run')


class PsDashContext(object):
    def __init__(self):
        self.logs = Logs()
        self.net_io_counters = NetIOCounters()


class PsDashApp(Flask):
    def __init__(self, *args, **kwargs):
        super(PsDashApp, self).__init__(*args, **kwargs)
        self.psdash = PsDashContext()


class PsDashRunner(object):
    @classmethod
    def create_from_args(cls, args=None):
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

        parsed = parser.parse_args(args)
        config = {}
        for k, v in vars(parsed).iteritems():
            key = 'PSDASH_%s' % k.upper() if k != 'debug' else 'DEBUG'
            config[key] = v

        return cls(config)

    def __init__(self, config=None):
        self.app = self._create_app(config)
        self._setup_logging()
        self._setup_context()

    def _create_app(self, config=None):
        app = PsDashApp(__name__)
        app.config.from_envvar('PSDASH_CONFIG', silent=True)

        if config and isinstance(config, dict):
            app.config.update(config)

        self._load_allowed_remote_addresses(app)

        # If the secret key is not read from the config just set it to something.
        if not app.secret_key:
            app.secret_key = 'whatisthissourcery'
        app.add_template_filter(filesizeformat)

        from psdash.web import webapp
        prefix = app.config.get('PSDASH_URL_PREFIX')
        if prefix:
            prefix = '/' + prefix.strip('/')
            webapp.url_prefix = prefix
        app.register_blueprint(webapp)

        return app

    def _load_allowed_remote_addresses(self, app):
        key = 'PSDASH_ALLOWED_REMOTE_ADDRESSES'
        addrs = app.config.get(key)
        if not addrs:
            return

        if isinstance(addrs, (str, unicode)):
            app.config[key] = [a.strip() for a in addrs.split(',')]

    def _setup_logging(self):
        level = self.app.config.get('PSDASH_LOG_LEVEL', logging.INFO) if not self.app.debug else logging.DEBUG
        format = self.app.config.get('PSDASH_LOG_FORMAT', '%(levelname)s | %(name)s | %(message)s')

        logging.basicConfig(
            level=level,
            format=format
        )
        logging.getLogger('werkzeug').setLevel(logging.WARNING if not self.app.debug else logging.DEBUG)

    def _start_interval(self, func, interval):
        def wrapper():
            self._start_interval(func, interval)
            func()
        t = threading.Timer(interval, wrapper)
        t.daemon = True
        t.start()
        
    def _setup_timers(self):
        netio_interval = self.app.config.get('PSDASH_NET_IO_COUNTER_INTERVAL', 3)
        self._start_interval(self.update_net_io_counters, netio_interval)

        logs_interval = self.app.config.get('PSDASH_LOGS_INTERVAL', 60)
        self._start_interval(self.reload_logs, logs_interval)

    def _setup_locale(self):
        # This set locale to the user default (usually controlled by the LANG env var)
        locale.setlocale(locale.LC_ALL, '')

    def _setup_context(self):
        self.app.psdash.net_io_counters.update()
        if 'PSDASH_LOGS' in self.app.config:
            self.app.psdash.logs.add_patterns(self.app.config['PSDASH_LOGS'])

    def reload_logs(self):
        logger.debug("Reloading logs...")
        return self.app.psdash.logs.add_patterns(self.app.config['PSDASH_LOGS'])

    def update_net_io_counters(self):
        logger.debug("Updating net io counters...")
        return self.app.psdash.net_io_counters.update()

    def run(self):
        logger.info('Starting psdash v0.4.0')

        self._setup_locale()
        self._setup_timers()
        
        logger.info('Listening on %s:%s', 
                    self.app.config['PSDASH_BIND_HOST'], 
                    self.app.config['PSDASH_PORT'])

        self.app.run(
            host=self.app.config['PSDASH_BIND_HOST'],
            port=self.app.config['PSDASH_PORT'],
            use_reloader=self.app.config.get('PSDASH_USE_RELOADER', False),
            threaded=True
        )


def main():
    r = PsDashRunner.create_from_args()
    r.run()
    

if __name__ == '__main__':
    main()