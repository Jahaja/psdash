import socket


def socket_constants(prefix):
    return dict((getattr(socket, n), n) for n in dir(socket) if n.startswith(prefix))


socket_families = socket_constants('AF_')
socket_types = socket_constants('SOCK_')
