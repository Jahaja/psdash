# psdash

psdash is a system information dashboard for linux using data mainly served by [psutil](https://code.google.com/p/psutil/) - hence the name. 

Features includes:
* **Overview**<br>
  Dashboard overview of the system displaying data on cpu, disks, network, users, memory, swap and network.
* **Processes**<br>
    List processes (`top` like) and view detailed process information about each process.

    Apart from a detailed process overview this is also available for each process:
    * Open files
    * Open connections
    * Memory maps
    * Child processes
    * Resource limits
* **Disks**<br>
    List data on all disks and partitions
* **Network**<br>
    List info on all network interfaces and the current throughput.
* **Logs**<br>
    Tail and search logs
* **All data is updated automatically, no need to refresh**

## Getting started

Installation using pip:<br>
`pip install psdash`

Installation from source:<br>
`python setup.py install`

Starting psdash:<br>
`psdash --log /var/log/myapp.log --log /var/log/mydb.log`

Available command-line arguments:
```
usage: psdash [-h] [-l path] [-b host] [-p port] [-d]

psdash 0.1.0 - system information web dashboard

optional arguments:
  -h, --help            show this help message and exit
  -l path, --log path   log files to make available for psdash. This option
                        can be used multiple times.
  -b host, --bind host  host to bind to. Defaults to 0.0.0.0 (all interfaces).
  -p port, --port port  port to listen on. Defaults to 5000.
  -d, --debug           enables debug mode.
```

## Screenshots

## License
Released under CC0 (Public Domain Dedication).

http://creativecommons.org/publicdomain/zero/1.0/
