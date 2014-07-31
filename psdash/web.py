# coding=utf-8
import logging
import psutil
import socket
from datetime import datetime, timedelta
import uuid
import locale
from flask import render_template, request, session, jsonify, Response, Blueprint, current_app
from psdash.net import get_interface_addresses
from psdash.helpers import socket_families, socket_types

logger = logging.getLogger('psdash.web')
webapp = Blueprint('psdash', __name__, static_folder='static')


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


def fromtimestamp(value, dateformat='%Y-%m-%d %H:%M:%S'):
    dt = datetime.fromtimestamp(int(value))
    return dt.strftime(dateformat)


def build_network_interfaces():
    io_counters = current_app.psdash.net_io_counters.get()
    addresses = get_interface_addresses()

    if io_counters:
        for inf in addresses:
            inf.update(io_counters.get(inf['name'], {}))

    return addresses


@webapp.before_request
def check_access():
    allowed_remote_addrs = current_app.config.get('PSDASH_ALLOWED_REMOTE_ADDRESSES')
    if allowed_remote_addrs:
        if request.remote_addr not in allowed_remote_addrs:
            current_app.logger.info(
                'Returning 401 for client %s as address is not in allowed addresses.',
                request.remote_addr
            )
            current_app.logger.debug('Allowed addresses: %s', allowed_remote_addrs)
            return 'Access denied', 401

    username = current_app.config.get('PSDASH_AUTH_USERNAME')
    password = current_app.config.get('PSDASH_AUTH_PASSWORD')
    if username and password:
        auth = request.authorization
        if not auth or auth.username != username or auth.password != password:
            return Response(
                'Access deined',
                401,
                {'WWW-Authenticate': 'Basic realm="psDash login required"'}
            )


@webapp.before_request
def setup_client_id():
    if 'client_id' not in session:
        client_id = uuid.uuid4()
        current_app.logger.debug('Creating id for client: %s', client_id)
        session['client_id'] = client_id


@webapp.errorhandler(psutil.AccessDenied)
def access_denied(e):
    errmsg = 'Access denied to %s (pid %d).' % (e.name, e.pid)
    return render_template('error.html', error=errmsg), 401


@webapp.errorhandler(psutil.NoSuchProcess)
def access_denied(e):
    errmsg = 'No process with pid %d was found.' % e.pid
    return render_template('error.html', error=errmsg), 404


@webapp.route('/')
def index():
    node = current_app.psdash
    sysinfo = node.get_sysinfo()
    uptime = timedelta(seconds=sysinfo['uptime'])
    uptime = str(uptime).split('.')[0]

    netifs = node.get_network_interfaces().values()
    netifs.sort(key=lambda x: x.get('bytes_sent'), reverse=True)

    data = {
        'os': sysinfo['os'].decode('utf-8'),
        'hostname': sysinfo['hostname'].decode('utf-8'),
        'uptime': uptime,
        'load_avg': sysinfo['load_avg'],
        'num_cpus': sysinfo['num_cpus'],
        'memory': node.get_memory(),
        'swap': node.get_swap_space(),
        'disks': node.get_disks(),
        'cpu': node.get_cpu(),
        'users': node.get_users(),
        'net_interfaces': netifs,
        'page': 'overview',
        'is_xhr': request.is_xhr
    }

    return render_template('index.html', **data)


@webapp.route('/processes', defaults={'sort': 'cpu_percent', 'order': 'desc'})
@webapp.route('/processes/<string:sort>')
@webapp.route('/processes/<string:sort>/<string:order>')
def processes(sort='pid', order='asc'):
    procs = current_app.psdash.get_process_list()
    procs.sort(
        key=lambda x: x.get(sort),
        reverse=True if order != 'asc' else False
    )

    return render_template(
        'processes.html',
        processes=procs,
        sort=sort,
        order=order,
        page='processes',
        is_xhr=request.is_xhr
    )


@webapp.route('/process/<int:pid>', defaults={'section': 'overview'})
@webapp.route('/process/<int:pid>/<string:section>')
def process(pid, section):
    valid_sections = [
        'overview',
        'threads',
        'files',
        'connections',
        'memory',
        'environment',
        'children',
        'limits'
    ]

    if section not in valid_sections:
        errmsg = 'Invalid subsection when trying to view process %d' % pid
        return render_template('error.html', error=errmsg), 404

    node = current_app.psdash

    context = {
        'process': node.get_process(pid),
        'section': section,
        'page': 'processes',
        'is_xhr': request.is_xhr
    }

    if section == 'environment':
        context['process_environ'] = node.get_process_environment(pid)
    elif section == 'threads':
        context['threads'] = node.get_process_threads(pid)
    elif section == 'files':
        context['files'] = node.get_process_open_files(pid)
    elif section == 'connections':
        context['connections'] = node.get_process_connections(pid)
    elif section == 'memory':
        context['memory_maps'] = node.get_process_memory_maps(pid)
    elif section == 'children':
        context['children'] = node.get_process_children(pid)
    elif section == 'limits':
        context['limits'] = node.get_process_limits(pid)

    return render_template(
        'process/%s.html' % section,
        **context
    )


def filter_connections(conns, filters):
    for k, v in filters.iteritems():
        if not v:
            continue

        if k in ('laddr', 'raddr'):
            conns = [c for c in conns if getattr(c, k) and str(getattr(c, k)[0]) == v]
        else:
            conns = [c for c in conns if str(getattr(c, k)) == v]

    return conns


@webapp.route('/network')
def view_networks():
    node = current_app.psdash
    netifs = node.get_network_interfaces().values()
    netifs.sort(key=lambda x: x.get('bytes_sent'), reverse=True)

    # {'key', 'default_value'}
    # An empty string means that no filtering will take place on that key
    form_keys = {
        'pid': '', 
        'family': socket_families[socket.AF_INET],
        'type': socket_types[socket.SOCK_STREAM],
        'state': 'LISTEN'
    }

    form_values = dict((k, request.args.get(k, default_val)) for k, default_val in form_keys.iteritems())

    for k in ('local_addr', 'remote_addr'):
        val = request.args.get(k, '')
        if ':' in val:
            host, port = val.rsplit(':', 1)
            form_values[k + '_host'] = host
            form_values[k + '_port'] = int(port)
        elif val:
            form_values[k + '_host'] = val

    conns = node.get_connections(form_values)
    conns.sort(key=lambda x: x['state'])

    states = [
        'ESTABLISHED', 'SYN_SENT', 'SYN_RECV',
        'FIN_WAIT1', 'FIN_WAIT2', 'TIME_WAIT',
        'CLOSE', 'CLOSE_WAIT', 'LAST_ACK',
        'LISTEN', 'CLOSING', 'NONE'
    ]

    return render_template(
        'network.html',
        page='network',
        network_interfaces=netifs,
        connections=conns,
        socket_families=socket_families,
        socket_types=socket_types,
        states=states,
        is_xhr=request.is_xhr,
        num_conns=len(conns),
        **form_values
    )


@webapp.route('/disks')
def view_disks():
    node = current_app.psdash
    disks = node.get_disks(all_partitions=True)
    io_counters = node.get_disks_counters().items()
    io_counters.sort(key=lambda x: x[1]['read_count'], reverse=True)
    return render_template(
        'disks.html',
        page='disks',
        disks=disks,
        io_counters=io_counters,
        is_xhr=request.is_xhr
    )


@webapp.route('/logs')
def view_logs():
    available_logs = current_app.psdash.get_logs()
    available_logs.sort(cmp=lambda x1, x2: locale.strcoll(x1['path'], x2['path']))

    return render_template(
        'logs.html',
        page='logs',
        logs=available_logs,
        is_xhr=request.is_xhr
    )


@webapp.route('/log')
def view_log():
    filename = request.args['filename']
    seek_tail = request.args.get('seek_tail', '1') != '0'
    session_key = session.get('client_id')

    try:
        content = current_app.psdash.read_log(filename, session_key=session_key, seek_tail=seek_tail)
    except KeyError:
        error_msg = 'File not found. Only files passed through args are allowed.'
        if request.is_xhr:
            return error_msg
        return render_template('error.html', error=error_msg), 404

    if request.is_xhr:
        return content

    return render_template('log.html', content=content, filename=filename)


@webapp.route('/log/search')
def search_log():
    filename = request.args['filename']
    query_text = request.args['text']
    session_key = session.get('client_id')

    try:
        data = current_app.psdash.search_log(filename, query_text, session_key=session_key)
        return jsonify(data)
    except KeyError:
        return 'Could not find log file with given filename', 404
