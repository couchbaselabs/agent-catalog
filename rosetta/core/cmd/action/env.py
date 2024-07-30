import json

def cmd_env(ctx):
    print(json.dumps(ctx, sort_keys=True, indent=4))
