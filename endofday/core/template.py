class ConfigGen(object):
    """
    Utility class for generating a config file from a jinja template.
    """
    def __init__(self, template_str):
        self.template_str = template_str

    def compile(self, configs, env):
        template = env.get_template(self.template_str)
        return template.render(configs)

    def generate_conf(self, configs, path, env):
        output = self.compile(configs, env)
        with open(path, 'w+') as f:
            f.write(output)
