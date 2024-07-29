import importlib.resources

def version():
    lines = importlib.resources.files('rosetta').joinpath('VERSION.txt').read_text().split('\n')
    return '\n'.join([line for line in lines if not line.startswith('#')]).strip()

def cmd_version():
    print(version())

if __name__ == "__main__":
    cmd_version()
