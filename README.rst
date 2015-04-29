========
endofday
========

Execute workflows of docker containers described in yaml files.


Quickstart
==========

The only dependency is ``docker`` and an image that is available from
the docker hub, so you do not need to clone this repository or
download anything. To get started:

1. Change into a directory where you will work and execute:

   .. code-block:: bash

      $ docker run -v $(pwd):/staging jstubbs/endofday --setup

   This command installs a single script ``endofday.sh`` in the
   current working directory.

2. Create a yaml file defining your workflow: specify which containers
   to run and define the inputs, outputs, and command. Use
   outputs from one container as inputs to another to create a
   dependency. You can also specify files on your local system to use
   as inputs. Use any image available locally or on the docker hub.
   Examples can be found in the examples directory of this
   repository. See the ``endofday.yml`` reference for more details.

3. Execute the workflow using the endofday.sh script:

   .. code-block:: bash

      $ ./endofday.sh my_workflow.yml


More Details
============

Suppose we found several Docker images that do part of the work in
which we are interested.  Each of the images would have its own way to
obtain inputs and to generate outputs.  The following diagram shows a
(fictitious) example and the associated ``endofday`` yaml file that
represents it.  Each block shows an individual image and the files
(relative to each container) which are expected as inputs and outputs.

.. sidebar:: Example

   .. image:: endofday.png
      :align: center
      :width: 100%


.. code-block:: yaml

   inputs:
     - input1 <- /home/user/input.txt

   outputs:
     - /data/output.txt

   processes:
     P:
       image: user/image_p
       inputs:
         - inputs.input1 -> /data/input_p.txt
       outputs:
         - /data/output_p_1.txt -> output_p_1
         - /data/output_p_2.txt -> output_p_2
       command: run_p

     N1:
       image: user/image_n1
       volumes:
         - /tmp
       inputs:
         - P.output_p_1 -> /tmp/input_n1.txt
       outputs:
         - /tmp/output_n1.txt -> output_n1
       command: run_n1

     N2:
       image: user/image_n2
       volumes:
         - /target
       inputs:
         - P.output_p_2 -> /target/input_n2.txt
       outputs:
         - /target/output_n2.txt -> output_n2
       command: run_n2

     S:
       image: user/image_s
       volumes:
         - /data
       inputs:
         - N1.output_n1 -> /data/a.txt
         - N2.output_n2 -> /data/b.txt
       outputs:
         - /data/output.txt
       command: run_s


Agave Integration
=================
We are building support for running endofday tasks on the Agave Platform's compute cloud. Initially, two use cases will be
supported: 1) executing entire workflows on the cloud and 2) farming out individual task computations to Agave as part
of a workflow running on your local machine.

After configuring endofday to use your Agave account for submitting jobs, you can execute an entire workflow on the
Agave cloud simply by executing:

   .. code-block:: bash

      $ ./endofday my_workflow.yml --agave

All docker containers will be executed on the Agave cloud and their outputs archived to your default storage system
or another storage system you configure. You can configure an email address to get a notification when the results
are ready.

Alternatively, you can instruct endofday to execute specific tasks on the Agave cloud as part of a larger workflow
executing on your local machine. The endofday engine will send instructions to Agave to run the specific container
and command in cloud after uploading all necessary dependencies to the storage system defined. Once the job completes,
endofday will download the results and continue executing the workflow.

To execute a specific task on the Agave cloud, specify 'agave' as the value for execution directly in the yaml
workflow definition file. For example, to run N2 on Agave we would update the above yaml file with this stanza:

.. code-block:: yaml
     .   .   .

     N2:
       image: user/image_n2
       execution: agave
       volumes:
         - /target
       inputs:
         - P.output_p_2 -> /target/input_n2.txt
       outputs:
         - /target/output_n2.txt -> output_n2
       command: run_n2


To use either approach, you first need an Agave account and an API client. If you don't have those already you can
get those here: http://preview.agaveapi.co/documentation/beginners-guides/

Configuration
-------------

Configure endofday to use your Agave credentials by adding the following fields to your endofday.conf file under
the Agave section.

.. code-block:: yaml
    [agave]
    # these configurations are only needed when running on the Agave platform

    # the base URL for the Agave tenant to use
    api_server: https://agave.iplantc.org

    # Agave username
    username: jstubbs
    # password: abc

    # client credentials
    client_name: test2
    client_key: 1VkZVI0cKVwuQfxKpPTtTkTOWEMa
    # client_secret: 123

    # storage system
    storage_system: data.iplantcollaborative.org

    # home directory for endofday. Each work flow execution will automatically get a directory within this directory.
    # Default is to use the Agave username.
    home_dir: jstubbs

