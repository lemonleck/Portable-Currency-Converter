import sysconfig


def pre_find_module_path(hook_api):
    hook_api.search_dirs = [sysconfig.get_path("stdlib")]
