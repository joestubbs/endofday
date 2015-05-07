========
Tutorial
========
In this tutorial we illustrate the main features of endofday by working through some simple examples at the
command line.


Setting Up
==========
The primary dependency for this tutorial is Docker and a few images available from the public Docker hub. To install
docker on your machine, refer to the official documentation_.

Once Docker is installed, install endofday by first pulling the official image:

.. code-block:: bash

   $ docker pull jstubbs/endofday

Create a directory for your endofday work and run the setup script there:

.. code-block:: bash

   $ mkdir eod; cd eod
   $ docker run -v $(pwd):/staging jstubbs/endofday --setup

Running --setup installs a small bash script, endofday.sh, as well as an example configuration file, endofday.conf, in
the current working directory. That's it - you are now ready to run endofday workflows on your local machine.

In order to execute tasks in the Agave cloud you will need an Agave account and API keys. To sign up for an Agave
account and generate your client keys, see the beginners_guides_.

Once you have your Agave credentials, update the endofday.conf file with the following fields inside the [agave]
section:
- username
- password
- client_name
- client_key
- client_secret

endofday will archive results of task executions to an Agave storage system. If you know the id of a storage system you
want Agave to use, you can specify it as the value of the storage_system configuration. Otherwise, endofday will attempt
to use a sensible default.


Running locally
===============
endofday can execute entire workflows on your local machine. To illustrate this, we are going to work through a simple
example that approximates the number pi using basic algebra. The example is a toy one, but it illustrates
how to use the main features of endofday. It also illustrates how to cast the map-reduce model of computation into the
endofday framework.

The basic idea behind our pi approximation is that, given a unit circle inscribed in a square, the ratio of the area of
the circle to the area of the square is
    pi*r^2/ (2r)^2 = pi*r^2/4r^2 = pi/4
Therefore, we can approximate pi as 4 times an approximation of (area of circle)/(area of square). We can approximate
the ratio of the areas by randomly picking coordinates (x,y) in [0,1] in determining if they are in the circle. The
ratio of the areas will then be well approximated by the ratio of points in the circle to points outside of the circle
for a sufficiently large selection of coordinates.

We're going to build a workflow to implement this approximation algorithm in three major steps:

1. create n lists of coordinates
2. n workers churn through their list and determine how many points are in the circle and how many are outside.
3. an agregate sums the results from step two and computes the final pi approximation.

We're The first task si



Running in Agave
================

This example shows how to run remotely in Agave_.


.. _Agave: http://agaveapi.co

.. _documentation http://docs.docker.com/installation/
.. _beginners-guides http://preview.agaveapi.co/documentation/beginners-guides/