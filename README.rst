========
endofday
========

Execute workflows of docker containers described in yaml files.


Quickstart
==========

The only dependency is ``docker`` and an image that is available from the docker
hub, so you do not need to clone this repository or download anything. To get started:

1. Change into a directory where you will work and execute:

   .. code-block:: bash
   
      $ docker run -v $(pwd):/staging jstubbs/endofday --setup

   This command installs a single script ``endofday.sh`` in the current working directory.

2. Create a yaml file defining your workflow: specify which containers to run and define the inputs, outputs, 
   volumes and more. Use outputs from one container as inputs to another to create a dependency. You can also 
   specify files on your local system to use as inputs. Use any image available locally or on the docker hub. 
   Examples can be found in the examples directory of this repository. See the ``endofday.yml`` reference for more details.

3. Execute the workflow using the endofday.sh script:

   .. code-block:: bash
   
      $ ./endofday.sh my_workflow.yml


More Details
============


