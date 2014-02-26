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

## Usage

##### Installation using pip:
`pip install psdash`

##### Starting psdash:
`psdash -log /var/log/myapp.log -log /var/log/mydb.log`

psdash will listen on port 5000 by default

## Screenshots

## License
Released under CC0 (Public Domain Dedication).

http://creativecommons.org/publicdomain/zero/1.0/
