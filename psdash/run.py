import gevent
from gevent.monkey import patch_all
patch_all()

from gevent.pywsgi import WSGIServer
import locale
import argparse
import logging
import socket
import urllib
import urllib2
from logging import getLogger
from flask import Flask
import zerorpc
from psdash import __version__
from psdash.node import LocalNode, RemoteNode
from psdash.web import fromtimestamp


logger = getLogger('psdash.run')


class PsDashRunner(object):
    DEFAULT_LOG_INTERVAL = 60
    DEFAULT_NET_IO_COUNTER_INTERVAL = 3
    DEFAULT_REGISTER_INTERVAL = 60
    DEFAULT_BIND_HOST = '0.0.0.0'
    DEFAULT_PORT = 5000
    LOCAL_NODE = 'localhost'

    @classmethod
    def create_from_cli_args(cls):
        return cls(args=None)

    def __init__(self, config_overrides=None, args=tuple()):
        self._nodes = {}
        config = self._load_args_config(args)
        if config_overrides:
            config.update(config_overrides)
        self.app = self._create_app(config)

        self._setup_nodes()
        self._setup_logging()
        self._setup_context()

    def _get_args(cls, args):
        parser = argparse.ArgumentParser(
            description='psdash %s - system information web dashboard' % __version__
        )
        parser.add_argument(
            '-l', '--log',
            action='append',
            dest='logs',
            default=None,
            metavar='path',
            help='log files to make available for psdash. Patterns (e.g. /var/log/**/*.log) are supported. '
                 'This option can be used multiple times.'
        )
        parser.add_argument(
            '-b', '--bind',
            action='store',
            dest='bind_host',
            default=None,
            metavar='host',
            help='host to bind to. Defaults to 0.0.0.0 (all interfaces).'
        )
        parser.add_argument(
            '-p', '--port',
            action='store',
            type=int,
            dest='port',
            default=None,
            metavar='port',
            help='port to listen on. Defaults to 5000.'
        )
        parser.add_argument(
            '-d', '--debug',
            action='store_true',
            dest='debug',
            help='enables debug mode.'
        )
        parser.add_argument(
            '-a', '--agent',
            action='store_true',
            dest='agent',
            help='Enables agent mode. This launches a RPC server, using zerorpc, on given bind host and port.'
        )
        parser.add_argument(
            '--register-to',
            action='store',
            dest='register_to',
            default=None,
            metavar='host:port',
            help='The psdash node running in web mode to register this agent to on start up. e.g 10.0.1.22:5000'
        )
        parser.add_argument(
            '--register-as',
            action='store',
            dest='register_as',
            default=None,
            metavar='name',
            help='The name to register as. (This will default to the node\'s hostname)'
        )

        return parser.parse_args(args)

    def _load_args_config(self, args):
        config = {}
        for k, v in vars(self._get_args(args)).iteritems():
            if v:
                key = 'PSDASH_%s' % k.upper() if k != 'debug' else 'DEBUG'
                config[key] = v
        return config

    def _setup_nodes(self):
        self.add_node(LocalNode())

        nodes = self.app.config.get('PSDASH_NODES', [])
        logger.info("Registering %d nodes", len(nodes))
        for n in nodes:
            self.register_node(n['name'], n['host'], int(n['port']))

    def add_node(self, node):
        self._nodes[node.get_id()] = node

    def get_local_node(self):
        return self._nodes.get(self.LOCAL_NODE)

    def get_node(self, name):
        return self._nodes.get(name)

    def get_nodes(self):
        return self._nodes

    def register_node(self, name, host, port):
        n = RemoteNode(name, host, port)
        node = self.get_node(n.get_id())
        if node:
            n = node
            logger.debug("Updating registered node %s", n.get_id())
        else:
            logger.info("Registering %s", n.get_id())
        n.update_last_registered()
        self.add_node(n)
        return n

    def _create_app(self, config=None):
        app = Flask(__name__)
        app.psdash = self
        app.config.from_envvar('PSDASH_CONFIG', silent=True)

        if config and isinstance(config, dict):
            app.config.update(config)

        self._load_allowed_remote_addresses(app)

        # If the secret key is not read from the config just set it to something.
        if not app.secret_key:
            app.secret_key = 'whatisthissourcery'
        app.add_template_filter(fromtimestamp)

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
        
    def _setup_workers(self):
        net_io_interval = self.app.config.get('PSDASH_NET_IO_COUNTER_INTERVAL', self.DEFAULT_NET_IO_COUNTER_INTERVAL)
        gevent.spawn_later(net_io_interval, self._net_io_counters_worker, net_io_interval)

        if 'PSDASH_LOGS' in self.app.config:
            logs_interval = self.app.config.get('PSDASH_LOGS_INTERVAL', self.DEFAULT_LOG_INTERVAL)
            gevent.spawn_later(logs_interval, self._logs_worker, logs_interval)

        if self.app.config.get('PSDASH_AGENT'):
            register_interval = self.app.config.get('PSDASH_REGISTER_INTERVAL', self.DEFAULT_REGISTER_INTERVAL)
            gevent.spawn_later(register_interval, self._register_agent_worker, register_interval)

    def _setup_locale(self):
        # This set locale to the user default (usually controlled by the LANG env var)
        locale.setlocale(locale.LC_ALL, '')

    def _setup_context(self):
        self.get_local_node().net_io_counters.update()
        if 'PSDASH_LOGS' in self.app.config:
            self.get_local_node().logs.add_patterns(self.app.config['PSDASH_LOGS'])

    def _logs_worker(self, sleep_interval):
        while True:
            logger.debug("Reloading logs...")
            self.get_local_node().logs.add_patterns(self.app.config['PSDASH_LOGS'])
            gevent.sleep(sleep_interval)

    def _register_agent_worker(self, sleep_interval):
        while True:
            logger.debug("Registering agent...")
            self._register_agent()
            gevent.sleep(sleep_interval)

    def _net_io_counters_worker(self, sleep_interval):
        while True:
            logger.debug("Updating net io counters...")
            self.get_local_node().net_io_counters.update()
            gevent.sleep(sleep_interval)

    def _register_agent(self):
        register_name = self.app.config.get('PSDASH_REGISTER_AS')
        if not register_name:
            register_name = socket.gethostname()

        url_args = {
            'name': register_name,
            'port': self.app.config.get('PSDASH_PORT', self.DEFAULT_PORT),
        }
        register_url = '%s/register?%s' % (self.app.config['PSDASH_REGISTER_TO'], urllib.urlencode(url_args))

        if 'PSDASH_AUTH_USERNAME' in self.app.config and 'PSDASH_AUTH_PASSWORD' in self.app.config:
            auth_handler = urllib2.HTTPBasicAuthHandler()
            auth_handler.add_password(
                realm='psDash login required',
                uri=register_url,
                user=self.app.config['PSDASH_AUTH_USERNAME'],
                passwd=self.app.config['PSDASH_AUTH_PASSWORD']
            )
            opener = urllib2.build_opener(auth_handler)
            urllib2.install_opener(opener)

        try:
            urllib2.urlopen(register_url)
        except urllib2.HTTPError as e:
            logger.error('Failed to register agent to "%s": %s', register_url, e)

    def _run_rpc(self):
        logger.info("Starting RPC server (agent mode)")

        if 'PSDASH_REGISTER_TO' in self.app.config:
            self._register_agent()

        service = self.get_local_node().get_service()
        self.server = zerorpc.Server(service)
        self.server.bind('tcp://%s:%s' % (self.app.config.get('PSDASH_BIND_HOST', self.DEFAULT_BIND_HOST),
                                          self.app.config.get('PSDASH_PORT', self.DEFAULT_PORT)))
        self.server.run()

    def _run_web(self):
        logger.info("Starting web server")
        log = 'default' if self.app.debug else None

        ssl_args = {}
        if self.app.config.get('PSDASH_HTTPS_KEYFILE') and self.app.config.get('PSDASH_HTTPS_CERTFILE'):
            ssl_args = {
                'keyfile': self.app.config.get('PSDASH_HTTPS_KEYFILE'),
                'certfile': self.app.config.get('PSDASH_HTTPS_CERTFILE')
            }

        listen_to = (
            self.app.config.get('PSDASH_BIND_HOST', self.DEFAULT_BIND_HOST),
            self.app.config.get('PSDASH_PORT', self.DEFAULT_PORT)
        )
        self.server = WSGIServer(
            listen_to,
            application=self.app,
            log=log,
            **ssl_args
        )
        self.server.serve_forever()

    def run(self):
        logger.info('Starting psdash v%s' % __version__)

        self._setup_locale()
        self._setup_workers()

        logger.info('Listening on %s:%s',
                    self.app.config.get('PSDASH_BIND_HOST', self.DEFAULT_BIND_HOST),
                    self.app.config.get('PSDASH_PORT', self.DEFAULT_PORT))

        if self.app.config.get('PSDASH_AGENT'):
            return self._run_rpc()
        else:
            return self._run_web()


def main():
    r = PsDashRunner.create_from_cli_args()
    r.run()
    

if __name__ == '__main__':
    main()