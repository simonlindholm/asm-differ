def apply(config, args):
    config["baseimg"] = "target.bin"
    config["myimg"] = "source.bin"
    config["mapfile"] = "build.map"
    config["source_directories"] = ["."]
    #config['arch'] = 'mips'
    #config['map_format'] = 'gnu' # gnu or mw
    #config['makeflags'] = []
    #config['objdump_executable'] = ''
