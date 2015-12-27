# tm_navigator workflow

This is how I set up the tm_navigator to work.

### Clone tm_navigator

`git clone https://github.com/omtcyf0/tm_navigator`

### `cd` to the directory with Dockerfile

`cd tm_navigator/docker`

### Build Docker image

`sudo docker build -t {IMAGE_NAME} .`

### Print info about your Docker images

`sudo docker images`

You should see something like this:

```
REPOSITORY             TAG                 IMAGE ID            CREATED             VIRTUAL SIZE
{IMAGE_NAME}           latest              {IMAGE_ID}          47 hours ago        684 MB
debian                 stable              45a21bba71ea        3 weeks ago         125.1 MB
```

### Run the Docker image

`sudo docker run {IMAGE_NAME}` or `sudo docker {IMAGE_ID}`

You will see something like this:

```
[s6-init] making user provided files available at /var/run/s6/etc...exited 0.
[s6-init] ensuring user provided files have correct perms...exited 0.
[fix-attrs.d] applying ownership & permissions fixes...
[fix-attrs.d] done.
[cont-init.d] executing container initialization scripts...
[cont-init.d] done.
[services.d] starting services
[services.d] done.
2015-12-27 10:03:03 UTC [159-1] LOG:  database system was shut down at 2015-12-25 10:31:34 UTC
2015-12-27 10:03:03 UTC [159-2] LOG:  MultiXact member wraparound protections are now enabled
2015-12-27 10:03:03 UTC [139-1] LOG:  database system is ready to accept connections
2015-12-27 10:03:03 UTC [163-1] LOG:  autovacuum launcher started
From https://github.com/omtcyf0/tm_navigator
   d1be1b2..d1a23e8  master     -> origin/master
Updating d1be1b2..d1a23e8
Fast-forward
 tm_navigator/templates/relations_views.html | 11 ++++++-----
 1 file changed, 6 insertions(+), 5 deletions(-)
 * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
 * Restarting with inotify reloader
 * Debugger is active!
 * Debugger pin code: 783-096-669
```

### Print info about your Docker containers

`sudo docker ps`

You should see something like this:

```
CONTAINER ID        IMAGE                         COMMAND             CREATED             STATUS              PORTS               NAMES
{CONTAINER_ID}      {IMAGE_NAME}:latest           "/init"             17 seconds ago      Up 16 seconds       22/tcp              {CONTAINER_NAME}
```

### Get information about the container IP adress

`sudo docker inspect {CONTAINER ID} | grep "IPAddress"` or ``sudo docker inspect {CONTAINER_NAME} | grep "IPAddress"`

You'll get the IP address the container is available from:

```
        "IPAddress": "172.17.0.2",
```

### Get an access to the shell inside the container

`sudo docker exec -i -t {CONTAINER_NAME} bash` or `sudo docker exec -i -t {CONTAINER_ID} bash`

### The end

Now you're all set! You can access the running Flask app via the {IP_ADDRESS}:5000, where {IP_ADDRESS} is the one you got previosly. and you can work using vim inside the container. Don't forget to push your changes before the container shutdown! It won't save the changes you made if you don't push them.
