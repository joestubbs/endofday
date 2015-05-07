========
Tutorial
========
In this tutorial we illustrate the main features of endofday by working through some simple examples at the
command line.


Setting Up
==========
The primary dependency for this tutorial is Docker and a few images available from the public Docker hub. To install
docker on your machine, refer to the official documentation_.

.. warning:: At the moment, endofday requires the latest version of Docker (1.6) to be installed. This is because
             endofday uses a local copy of Docker 1.6 to execute containers on the host, and Docker requires
             the version of client and server to match. If you want to use an older version of Docker, you can mount
             the binary into the endofday container at runtime.

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

Once you have your Agave credentials, update the endofday.conf file with the following fields inside the agave section:

    - ``username``
    - ``password``
    - ``client_name``
    - ``client_key``
    - ``client_secret``

endofday will archive results of task executions to an Agave storage system. If you know the id of a storage system you
want Agave to use, you can specify it as the value of the storage_system configuration. Otherwise, endofday will attempt
to use a sensible default.


Running Locally
===============
endofday can execute entire workflows on your local machine. To illustrate this, we are going to work through a simple
example that approximates the number pi using basic algebra. The example is a toy one, but it illustrates
how to use the main features of endofday. It also illustrates how to cast the map-reduce model of computation into the
endofday framework.

The basic idea behind our pi approximation is that, given a unit circle inscribed in a square, the ratio of the area of
the circle to the area of the square is
    .. math::
       \pi*r^2/ (2r)^2 = \pi*r^2/4r^2 = \pi/4

Therefore, we can approximate pi as 4 times an approximation of (area of circle)/(area of square). We can approximate
the ratio of the areas by randomly picking coordinates (x,y) in [0,1] in determining if they are in the circle by
checking the algebraic equation for a circle we all learned in elementary: x^2 + y^2 = 1. The
ratio of the areas will then be well approximated by the ratio of points in the circle to points outside of the circle
for a sufficiently large selection of coordinates.

We're going to build a workflow to implement this approximation algorithm in three main steps:

1. Create n lists of coordinates to process.
2. Run n workers, one for each list produced in step 1, to determine how many points in the list are in the circle
(and how many are outside).

3. Run an "aggregator" to sum the results from step two and computes the final pi approximation.

By the end of this section we will have created a complete YAML workfile description that we can use to execute
the workflow. To get started, create a new text file called approximate_pi.yml (or something similar), and add the
following:

.. code-block:: bash

   ---
   name: approximate_pi

This line simply supplies a name to our workflow. The name attribute is required but it can be any valid string.


Global Inputs & Outputs
=======================

Luckily for us, there are Docker images on the public hub available for each of these tasks. For step 1, we'll use the
``jstubbs/genpoints`` image to generate lists of random coordinates for us.

All input files in an endofday workflow are either global inputs or outputs from another task. We know from the
documentation of the genpoints program that the number of lists and the number of coordinates in each
list to be generated can be configured by supplying a configration file to the genpoints program. We can specify such
a configuration file as a global input to the entire workflow. To do so, we create add an ``inputs`` collection just
below the workflow name and add our input file:

.. code-block:: bash

   ---
   name: approximate_pi

   inputs:
       - input <- genpoints.conf

To define the global input we provide two values - label and source - separated by ``<-``. In this case, the label is
simply "input". The label can be whatever we want, but it should be unique so that we can use it to reference the input
in other sections of the workflow definition. The source attribute, in this case "genpoints.conf", tells endofday
where to find the file. Here we have provided a relative path so endofday looks in the current working
directory. Alternatively, we could have provided any absolute path on the file system.

We also need to create the genpoints.conf file.  All we have to do is supply the number of files and the number of
coordinates per file we want the genpoints program to generate. Since each file will be parsed in its own process, we'll
choose to create four files and generate 10,000 coordinates in each. Here is what the config file should like like:

.. code-block:: bash

    [genpoints]

    files: 4
    coords: 10000


Similarly, we can define global outputs for the workflow by listing outputs from specific tasks in the workflow.
This feature is mainly useful as documentation (you are declaring this output to be a "final" output, not just an
intermediate result) of your workflow. It's also useful for making workflows composable, though this feature is still
experimental.

.. code-block:: bash

   ---
   name: approximate_pi

   inputs:
       - input <- genpoints.conf

   outputs:
       - approx_pi.pi


Processes
=========

The heart of a workflow is the set of processes or tasks that will be invoked. Each process defines a Docker image to
execute, a command to execute in the container, inputs and outputs for the container, and (optionally) a description
of the task. Here is the process definition for the first step in our workflow:

.. code-block:: bash

    processes:
        generate_coords:
            image: jstubbs/genpoints
            description: creates lists of randomly generated coordinates from [0,1]
            inputs:
                - inputs.input -> /data/gen.conf
            outputs:
                - /data/out_0 -> out_0
                - /data/out_1 -> out_1
                - /data/out_2 -> out_2
                - /data/out_3 -> out_3
            command: python ./genpoints.py -p /data/gen.conf

We've created a new entry in the processes section called ``generate_coords`` which is just a label for our process. It
can be anything as long as it is unique across the workflow. The ``image`` and ``description`` fields are
self explanitory. In the input section, we list all file inputs to the process. Here we have specified that we want to
use the input labeled "input" from the "inputs" section and we want to map it to the path "/data/gen.conf" in the
jstubbs/genpoints container. We could have mapped it anywhere in the container - endofday will take of mounting the
Docker volumes properly at runtime.

The outputs section is similar - we list all the outputs we expect from this container invocation in terms of their
paths in the container, and we assign each a unique label (unique within the outputs of this process). We happen to
know from our experience running the genpoints container that it stores the outputs in the ``/data`` directory and
labels them ``out_0`` through ``out_n``. In this case we configured it to generate four files.

Finally, the ``command`` value is what is actually passed to the ``docker run`` statement. We are executing the
genpoints script and passing a single argument - the location of our config file.


Task Dependencies
=================

We create task dependencies by declaring outputs from one task to be inputs to another task. For step 2 in our workflow
we will use the ``jstubbs/ctpts`` image to process the outputs created from the generate_coords task. There will be
four such processes since four outputs were created in step 1.

.. code-block:: bash

    processes:
        generate_coords:
            image: jstubbs/genpoints
            description: creates lists of randomly generated coordinates from [0,1]
            inputs:
                - inputs.input -> /data/gen.conf
            outputs:
                - /data/out_0 -> out_0
                - /data/out_1 -> out_1
                - /data/out_2 -> out_2
                - /data/out_3 -> out_3
            command: python ./genpoints.py -p /data/gen.conf

        count_points_0:
            image: jstubbs/ctpts
            inputs:
                - generate_coords.out_0 -> /tmp/input
            outputs:
                - /tmp/output -> out
            command: python ./ctpoints.py -p /tmp/input

        count_points_1:
            image: jstubbs/ctpts
            inputs:
                - generate_coords.out_1 -> /tmp/input
            outputs:
                - /tmp/output -> out
            command: python ./ctpoints.py -p /tmp/input

        count_points_2:
            image: jstubbs/ctpts
            inputs:
                - generate_coords.out_2 -> /tmp/input
            outputs:
                - /tmp/output -> out
            command: python ./ctpoints.py -p /tmp/input

        count_points_3:
            image: jstubbs/ctpts
            inputs:
                - generate_coords.out_3 -> /tmp/input
            outputs:
                - /tmp/output -> out
            command: python ./ctpoints.py -p /tmp/input

Note the input section of each of our count_points tasks: they refer to an output from the generate_coords task, but
this is the only input to the task. As a result, each count_points task depends on the generate_coords task, but none
of them depend on each other.

Approximating Pi
================

Finally, we'll use the ``jstubbs/apprxpi`` image to combine the results from step 2 and produce the final approximation.
This task will depend on all of the count_point tasks, as evidenced by the input section. Putting everything together
we now have a complete workflow:

.. code-block:: bash

   ---
   name: approximate_pi

   inputs:
       - input <- genpoints.conf

   outputs:
       - approx_pi.pi

    processes:
        generate_coords:
            image: jstubbs/genpoints
            description: creates lists of randomly generated coordinates from [0,1]
            inputs:
                - inputs.input -> /data/gen.conf
            outputs:
                - /data/out_0 -> out_0
                - /data/out_1 -> out_1
                - /data/out_2 -> out_2
                - /data/out_3 -> out_3
            command: python ./genpoints.py -p /data/gen.conf

        count_points_0:
            image: jstubbs/ctpts
            inputs:
                - generate_coords.out_0 -> /tmp/input
            outputs:
                - /tmp/output -> out
            command: python ./ctpoints.py -p /tmp/input

        count_points_1:
            image: jstubbs/ctpts
            inputs:
                - generate_coords.out_1 -> /tmp/input
            outputs:
                - /tmp/output -> out
            command: python ./ctpoints.py -p /tmp/input

        count_points_2:
            image: jstubbs/ctpts
            inputs:
                - generate_coords.out_2 -> /tmp/input
            outputs:
                - /tmp/output -> out
            command: python ./ctpoints.py -p /tmp/input

        count_points_3:
            image: jstubbs/ctpts
            inputs:
                - generate_coords.out_3 -> /tmp/input
            outputs:
                - /tmp/output -> out
            command: python ./ctpoints.py -p /tmp/input

        approx_pi:
            image: jstubbs/apprxpi
            inputs:
                - count_points_0.out -> /data/out_0
                - count_points_1.out -> /data/out_1
                - count_points_2.out -> /data/out_2
                - count_points_3.out -> /data/out_3
            outputs:
                - /tmp/pi -> out
            command: python ./apprxpi.py -p /data


We can execute this workflow by issuing the following command:

.. code-block:: bash

    $ ./endofday.sh approximate_pi.yml

The result of running this computation looks something like:

.. code-block:: bash

    Using multiprocessing with 8 processes.
    creating:  /staging/approx_pi/generate_coords/data
    .  generate_coords
    .  count_points_0
    creating:  /staging/approximate_pi/count_points_0/tmp
    creating:  /staging/approximate_pi/count_points_1/tmp
    creating:  /staging/approximate_pi/count_points_3/tmp
    .  count_points_1
    .  count_points_2
    creating:  /staging/approximate_pi/count_points_2/tmp
    .  count_points_3
    .  approx_pi
    creating:  /staging/approximate_pi/approx_pi/tmp
    3.14219

You'll notice that endofday created a directory called approximate_pi in the current working directory, and inside
approximate_pi will be directories for each task that was executed. Within each subdirectory are all the outputs
generated by the task. For instance, inside ``approximate_pi/count_points_2/tmp`` you should see a file called output.


Running in Agave
================

There are two ways to run endofday tasks in the Agave cloud. The first is by specifying an execution type of "agave"
directly in the YAML file within the stanza for a given task. For example, we could execute the ``count_points_1`` task
in the Agave cloud by simply changing our workflow definition as follows:

.. code-block:: bash

        count_points_1:
            image: jstubbs/ctpts
            execution: agave
            inputs:
                - generate_coords.out_1 -> /tmp/input
            outputs:
                - /tmp/output -> out
            command: python ./ctpoints.py -p /tmp/input

In this case, endofday will start executing the workflow on your local machine. When it comes time to execute the
count_points_1 task, endofday will upload all necessary inputs for this task to the Agave storage system you have
configured and then submit a job to execute the Docker container on those inputs. When the job finishes, the outputs
(in this case ``/tmp/output``) will be downloaded to your local machine just as if the execution had occurred locally.
Other than some additional outputs indicating interactions with the Agave cloud, hybrid cloud execution should be
transparent to the user.

.. warning:: Because of the overhead of transferring files to and from the Agave cloud, in certain cases executing
             single tasks remotely can take significantly longer than executing locally.

Alternatively, an entire endofay workflow can be executed in the Agave cloud. To do so, simply pass the ``--agave``
flag when running endofday, e.g.

.. code-block:: bash

    $ ./endofday.sh --agave approximate_pi.yml

Here, endofday will upload all global inputs to the Agave storage system and submit a job to execute the entire
workflow. The endofday process exits as soon as the job is submitted. When the job completes, the results are
automatically archived to your storage system. By specifying an address for ``email`` in your agave configuration in
endofday, you will recieve an email when the outputs are available.


Specifying Global Inputs As URIs
================================

One advantage to running entire workflow in the Agave cloud is that you can specify your global inputs as URIs. This
includes "agave" urls of the form ``agave://my.storage.system.id//path/to/file`` as well as any publicly available URI
via a supported transport. For the list of supported transfer protocols, see the Agave documentation: http://preview.agaveapi.co/documentation/tutorials/data-management-tutorial/#importing-data

Here's an example of an alternative global inputs section for the approximate pi workflow that references an input file
in an Agave storage system:

.. code-block:: bash

   ---
   name: approximate_pi

   inputs:
       - input <- agave://endofday.local.storage.com//data/genpoints.conf




.. _Agave: http://agaveapi.co

.. _documentation http://docs.docker.com/installation/
.. _beginners-guides http://preview.agaveapi.co/documentation/beginners-guides/