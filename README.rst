endofday
========

Execute workflows of docker containers described in yaml files.


Quickstart
==========

The only dependency is ``docker`` and an image is available from the docker
hub, so you do not need to clone this repository or download anything. To get started:

1. Change into a directory where you will work and execute:

       $ docker run -v $(pwd):/staging jstubbs/endofday setup

  *This command installs a single script, endofday.sh, in the current working directory.

2. Create a yaml file defining your workflow: specify which containers to run and define the inputs, outputs, volumes and more. Use outputs from one container as inputs to another to create a dependency. You can also specify files on your local system to use as inputs.

```yaml
processes:
    bwa-mem:
        image: bwa:latest
        description: Align my paired-end reads to my reference.
        volumes:
            - /data
        inputs:
            - /home/joe/data/read1.fq:/data/fa1.fq   # <-- absolute path refers to localhost
            - /home/joe/data/read1.fq:/data/fa1.fq:/data/fa2.fq
            - /home/joe/refs/myref.fasta:/data/ref.fasta
        outputs:
            - /data/algn.sam   # <-- produced by container
        command: python bwa.py mem /data/ref.fasta /data/fa1.fq /data/fa2.fq > /data/algn.sam

    picard-s2b:
        image: picard:latest
        description: Convert sam to bam
        volumes:
            - /data
        inputs:
            - bwa-mem/data/algn.sam:/data/input.sam   # <-- refers to output from step 1
        outputs:
            - /data/output.bam
        command: java -jar SortSam.jar INPUT=/data/input.bam OUTPUT=/data/output.bam SORT_ORDER=coordinate

    gatk-indel:
        image: jstubbs/gatk
        descrition: Find indels using gatk
        volumes:
            - /data
        inputs:
            - picard-s2b/data/output.bam:/data/in.bam
            - /home/joe/data/realigner.intervals:/data/realigner.intervals
            - /home/joe/refs/myref.fasta:/data/ref.fasta
            - /home/joe/refs/1000G_phase1.indels.b37.vcf:/data/known_indels_1.vfc
            - /home/joe/refs/Mills_and_1000G_gold_standard.indels.b37.vcf:/data/known_indels_2.vfc
        outputs:
            - /data/output.bam
        command: java gatk.jar -T RealignerTargetCreator -R /data/ref.fasta -I in.bam -known known_indels.vfc -known known_indels_2.vfc -o realigner.intervals
```
  *Use any image available locally or on the docker hub. Examples can be found in the examples directory of this repository. See the endofday.yml reference for more details.

3. Execute the workflow using the endofday.sh script:

       $ ./endofday.sh my_workflow.yml


More Details
============


