"""
Generate a nexflow script from a declarative yaml file.
"""

import argparse
import os
import sys

from collections import OrderedDict
import jinja2
import yaml

TEMPLATE = '/endofday/nf.j2'
NEXTFLOW_BASE = os.environ.get('STAGING') or '/staging'
HOST_BASE = os.environ.get('STAGING_DIR') or '/staging'

class ConfigGen(object):
    """
    Utility class for generating a config file from a jinja template.
    """
    def __init__(self, template_str):
        self.template_str = template_str

    def generate_conf(self, configs, path, env):
        template = env.get_template(self.template_str)
        output = template.render(configs)
        with open(path, 'w+') as f:
            f.write(output)


class Process(object):
    """
    Represents a nextflow process.
    """
    def __init__(self, nf_base, host_base, name, desc, gloabl_outputs):
        self.nf_base = nf_base
        self.host_base = host_base
        self.name = name
        self.image = desc.get('image')
        self.command = desc.get('command')
        self.outputs = self.set_outputs(desc.get('outputs'))
        self.inputs = self.set_inputs(desc.get('inputs'), gloabl_outputs)
        self.volumes = self.set_volumes(desc.get('volumes'))

    def set_volumes(self, volumes_desc):
        """
        Return LOD of volumes for compiling j2 template. Each volume needs:
            container_path
            host_path
        """
        result = []
        for volume_desc in volumes_desc:
            volume = {'container_path': volume_desc}
            volume['host_path'] = os.path.join(self.nf_base, self.name, volume_desc[1:])
            volume['docker_volume_path'] = os.path.join(self.host_base, self.name, volume_desc[1:])
            result.append(volume)
        return result

    def set_inputs(self, inputs_desc, global_outputs):
        """
        Return LOD of inputs for compiling j2 template. Each input needs:
            name
            var_id
            from
            host_path
            container_path
        """
        result = []
        for idx, input_desc in enumerate(inputs_desc):
            input = {'name': self.name + "_input_" + str(idx)}
            input['var_id'] = 'x_' + str(idx)
            paths = input_desc.split(':')
            input['host_path'] = os.path.join(self.nf_base, paths[0])
            input['docker_volume_path'] = os.path.join(self.host_base, paths[0])
            input['container_path'] = paths[1]
            if paths[0].startswith('/'):
                # absolute paths refer to the host so use its own name for 'from':
                input['from'] = input['name']
            else:
                # relative paths refer to other processes so look up in outputs:
                for out in global_outputs:
                    # import pdb; pdb.set_trace()
                    if out['host_path'] == paths[0]:
                        input['from'] = out['name']
                        break
            result.append(input)
        return result

    def set_outputs(self, outputs_desc):
        """
        Return LOD of outputs for compiling j2 template. Each output needs:
            name
            host_path
        """
        result = []
        for idx, output_desc in enumerate(outputs_desc):
            output = {'name': self.name + "_output_" + str(idx)}
            if output_desc.startswith('/'):
                output_desc = output_desc[1:]
            output['host_path'] = os.path.join(self.nf_base, self.name, output_desc)
            result.append(output)
        return result

    def to_dict(self):
        return {'name': self.name,
                'inputs': self.inputs,
                'outputs': self.outputs,
                'volumes': self.volumes,
                'image': self.image,
                'command': self.command,
                }


def ordered_load(stream, Loader=yaml.Loader, object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)

def get_outputs(nf_base, proc_dict):
    result = []
    for name, desc in proc_dict.items():
        outputs = desc.get('outputs')
        out = {}
        for idx, output_desc in enumerate(outputs):
            if output_desc.startswith('/'):
                output_desc = output_desc[1:]
            out['host_path'] = os.path.join(name, output_desc)
            out['name'] = name + "_output_" + str(idx)
        result.append(out)
    return result

def get_inputs(proc_dict):
    inputs = []
    for name, desc in proc_dict.items():
        inputs_desc = desc.get('inputs')
        for idx, input_desc in enumerate(inputs_desc):
            paths = input_desc.split(':')
            inp = {'name': name + '_input_' + str(idx)}
            if paths[0].startswith('/'):
                inp['host_path'] = paths[0]
                inputs.append(inp)
    return inputs

def parse_yaml(yaml_file, nf_base, host_base):
    path = os.path.join(os.getcwd(), yaml_file)
    if not os.path.exists(path):
        sys.exit("Could not find input file: " + str(path))
    with open(path) as f:
        # src = yaml.load(f)
        src = ordered_load(f)
    proc_dict = src.get('processes')
    if not proc_dict:
        sys.exit("No processes defined.")
    outputs = get_outputs(nf_base, proc_dict)
    inputs = get_inputs(proc_dict)
    processes = []
    for name, desc in proc_dict.items():
        process = Process(nf_base, host_base, name, desc, outputs)
        processes.append(process.to_dict())
    return processes, os.path.basename(path), inputs

def main(yaml_file):
    processes, basename, inputs = parse_yaml(yaml_file, NEXTFLOW_BASE, HOST_BASE)
    # generate a script with the same name as the .yml but with a .nf extension instead:
    outfile = basename[:basename.rfind('.yml')] + '.nf'
    conf = ConfigGen(TEMPLATE)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.getcwd()), trim_blocks=True, lstrip_blocks=True)
    context = {'nextflow_base': NEXTFLOW_BASE,
               'processes': processes,
               'inputs': inputs}
    conf.generate_conf(context, outfile, env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generates nextflow script from yaml description.')
    parser.add_argument('yaml_file', type=str,
                        help='Yaml file to parse')
    args = parser.parse_args()
    main(args.yaml_file)