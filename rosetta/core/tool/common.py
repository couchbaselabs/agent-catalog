import pathlib


def get_front_matter_from_dot_sqlpp(filename: pathlib.Path):
    with filename.open('r') as fp:
        # TODO (GLENN): Harden this step.
        front_lines = []
        is_scanning = False
        for line in fp:
            if line.strip().startswith('/*'):
                is_scanning = True
            elif line.strip().endswith('*/'):
                break
            elif is_scanning:
                front_lines.append(line)
    return '\n'.join(front_lines)
