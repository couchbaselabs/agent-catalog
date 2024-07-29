import importlib.resources

def get_version():
    lines = importlib.resources.files('rosetta').joinpath('VERSION.txt').read_text().split('\n')
    return '\n'.join([line for line in lines if not line.startswith('#')]).strip()

if __name__ == "__main__":
    print(get_version())
