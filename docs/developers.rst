==========
Developers
==========
This section is intended for developers wishing to understand the inner-workings of eod. The information it contains is
not necessary for using the tool.

=================
Overview & Layout
=================
The eod functionality is provided through two docker containers: eod and eod_job_submit.


=====
Tasks
=====
The tasks.py module is at the heart of the eod functionality. Its main() function is the entrypoint for the eod
docker container (launched by endofday.sh) except when the `--agave` flag is issued, in which case the agaverun.py
module's main() function is entered.

At a high level, the tasks module does the following, in order:
1. Initial setup and command line args parsing
2. Iterate over user-supplied yaml file, creating Task objects for each task defined in the yaml file. These
will either be SimpleDockerTask objects (in case `image` is supplied) or AgaveAppTask objects (in case `app_id` is
supplied).
3. Iterate over task list generated in 2) to set the input and output volume mounts for each task.
4. Execute the doit engine with the provided list of tasks and the DockerLoaded task loader.

One key point is that the input volume mounts cannot be set until all tasks have been created. A volume mount is simply
a pair: (host path, container path), and the issue is to resolve the host path from the user supplied description of its
source (which will either refer to a global input or a task output). In case the source references the output of another
task, the host path for the input will reference the same host path as the output, so as to not have to copy files
around on the system. Therefore, by constructing all tasks first, we know we can find the host path for all inputs.
This resolution happens in the global resolve_source() function.


AgaveAppTask objects
====================
AgaveAppTask objects represent tasks that launch an Agave job to execute an app on a remote server. They maintain a list
of AgaveAppTaskOutput and AgaveAppTaskInput objects, which are wrappers around the basic TaskInput and TaskOuput objects.

AddedInputs - these
