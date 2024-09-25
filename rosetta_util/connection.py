def get_host_name(url: str):
    split_url = url.split("//")
    num_elements = len(split_url)
    if num_elements == 2:
        return split_url[1]
    elif num_elements == 1:
        return split_url[0]
    else:
        return ""
