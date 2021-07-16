def apply(config, args):
    config["baseimg"] = "target.bin"
    config["myimg"] = "source.bin"
    config["mapfile"] = "build.map"
    config["source_directories"] = ["."]
    # config["arch"] = "mips"
    # config["map_format"] = "gnu" # gnu or mw
    # config["mw_build_dir"] = "build/" # only needed for mw map format
    # config["makeflags"] = []
    # config["objdump_executable"] = ""
    # config["browser"] = '"/mnt/c/Program Files/Mozilla Firefox/firefox.exe" "file://///wsl$/Ubuntu-18.04/home/user/asm-differ/client.html"'
