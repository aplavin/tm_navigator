FROM aplavin/baseimage:0.9.17
MAINTAINER Alexander Plavin (alexander@plav.in)
CMD ["/sbin/my_init"]

RUN apt-get update && apt-get upgrade -y && apt-get install -y nano mc
RUN apt-get install --no-install-recommends -y \
    postgresql postgresql-contrib libpq-dev python3.5 python3.5-dev mercurial build-essential
RUN curl https://bootstrap.pypa.io/get-pip.py | python3.5

RUN apt-get install -y libopenblas-dev gfortran libhdf5-dev
RUN ln -s /usr/lib/x86_64-linux-gnu/libhdf5_cpp.so /usr/lib/x86_64-linux-gnu/libhdf5.so
RUN pip3.5 install --no-use-wheel cython numpy scipy
RUN pip3.5 install --global-option=build_ext --global-option="-I/usr/include/hdf5/serial" --global-option="-L/usr/lib/x86_64-linux-gnu/hdf5/serial" h5py

ENV VERSION 1.1
RUN cd /root && hg clone https://bitbucket.org/aplavin/tm_navigator
RUN cd /root/tm_navigator && LC_ALL=en_US.UTF-8 pip install --no-use-wheel --editable .

RUN mkdir /etc/service/postgresql
COPY postgresql.sh /etc/service/postgresql/run
RUN mkdir /etc/service/tm_navigator
COPY tm_navigator.sh /etc/service/tm_navigator/run

RUN rm -f /etc/service/sshd/down
RUN echo 'root:tmnavartmdev' | chpasswd
RUN sed -i 's/#PermitRootLogin yes/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
EXPOSE 22

RUN mkdir /var/run/postgresql/9.4-main.pg_stat_tmp/
RUN chown postgres /var/run/postgresql/9.4-main.pg_stat_tmp/

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
