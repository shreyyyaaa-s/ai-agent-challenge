# parser_registry.py
import importlib.util
import os

PARSER_REGISTRY = {}

def load_parsers():
    parser_dir = "custom_parsers"
    for filename in os.listdir(parser_dir):
        if filename.endswith("_parser.py"):
            bank = filename.replace("_parser.py", "")
            module_path = os.path.join(parser_dir, filename)
            spec = importlib.util.spec_from_file_location(bank, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "parse"):
                PARSER_REGISTRY[bank] = module.parse
            else:
                print(f" Warning: {filename} has no `parse()` function")

load_parsers()
